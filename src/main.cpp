#include <mpi.h>
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using Vec = std::vector<double>;
struct Metrics { double compute=0, halo=0, reduction=0, total=0; long halos=0, reductions=0; int iterations=0, checks=0; double residual=0; bool ok=false;
#ifdef HEAT_DIAGNOSTICS
double recursive_residual=0;
#endif
};
struct Grid {
    MPI_Comm comm; int rank, size, dims[2]={0,0}, coord[2], neighbors[4], nx, ny, ox, oy, stride;
    double r;
    Grid(int n,double r_):r(r_) {
        MPI_Comm_size(MPI_COMM_WORLD,&size); MPI_Dims_create(size,2,dims);
        if(n<dims[0] || n<dims[1]) throw std::runtime_error("N smaller than process grid");
        int periods[2]={0,0}; MPI_Cart_create(MPI_COMM_WORLD,2,dims,periods,0,&comm);
        MPI_Comm_rank(comm,&rank); MPI_Cart_coords(comm,rank,2,coord);
        MPI_Cart_shift(comm,0,1,&neighbors[0],&neighbors[1]); MPI_Cart_shift(comm,1,1,&neighbors[2],&neighbors[3]);
        nx=n/dims[0]+(coord[0]<n%dims[0]); ny=n/dims[1]+(coord[1]<n%dims[1]);
        ox=coord[0]*(n/dims[0])+std::min(coord[0],n%dims[0]);
        oy=coord[1]*(n/dims[1])+std::min(coord[1],n%dims[1]); stride=ny+2;
    }
    size_t at(int i,int j) const { return static_cast<size_t>(i)*stride+j; }
    Vec field() const { return Vec(static_cast<size_t>(nx+2)*(ny+2),0); }
    template<class F> void each(F f) const { for(int i=1;i<=nx;i++) for(int j=1;j<=ny;j++) f(at(i,j)); }
    void apply(Vec &x,Vec &out,Metrics &m) const {
        double t=MPI_Wtime(); Vec left(nx),right(nx),fromleft(nx,0),fromright(nx,0);
        for(int i=1;i<=nx;i++) { left[i-1]=x[at(i,1)]; right[i-1]=x[at(i,ny)]; }
        std::fill(x.begin(),x.begin()+stride,0); std::fill(x.begin()+at(nx+1,0),x.end(),0);
        for(int i=1;i<=nx;i++) x[at(i,0)]=x[at(i,ny+1)]=0;
        m.compute+=MPI_Wtime()-t; t=MPI_Wtime();
        MPI_Sendrecv(&x[at(1,1)],ny,MPI_DOUBLE,neighbors[0],10,&x[at(nx+1,1)],ny,MPI_DOUBLE,neighbors[1],10,comm,MPI_STATUS_IGNORE);
        MPI_Sendrecv(&x[at(nx,1)],ny,MPI_DOUBLE,neighbors[1],11,&x[at(0,1)],ny,MPI_DOUBLE,neighbors[0],11,comm,MPI_STATUS_IGNORE);
        MPI_Sendrecv(left.data(),nx,MPI_DOUBLE,neighbors[2],12,fromright.data(),nx,MPI_DOUBLE,neighbors[3],12,comm,MPI_STATUS_IGNORE);
        MPI_Sendrecv(right.data(),nx,MPI_DOUBLE,neighbors[3],13,fromleft.data(),nx,MPI_DOUBLE,neighbors[2],13,comm,MPI_STATUS_IGNORE);
        m.halo+=MPI_Wtime()-t; m.halos++; t=MPI_Wtime();
        for(int i=1;i<=nx;i++) { x[at(i,0)]=fromleft[i-1]; x[at(i,ny+1)]=fromright[i-1]; }
        for(int i=1;i<=nx;i++) for(int j=1;j<=ny;j++) { auto k=at(i,j); out[k]=(1+4*r)*x[k]-r*(x[k-stride]+x[k+stride]+x[k-1]+x[k+1]); }
        m.compute+=MPI_Wtime()-t;
    }
    double dot(const Vec &a,const Vec &b,Metrics &m) const {
        double t=MPI_Wtime(), local=0, global=0; each([&](size_t k){local+=a[k]*b[k];}); m.compute+=MPI_Wtime()-t;
        t=MPI_Wtime(); MPI_Allreduce(&local,&global,1,MPI_DOUBLE,MPI_SUM,comm); m.reduction+=MPI_Wtime()-t; m.reductions++; return global;
    }
};
struct Options { int n=512,steps=5,max_iter=10000,check=10,warmup=1,trial=1; double alpha=1,r=2,tol=1e-8; std::string solver="jacobi",init="gaussian",output="",dump=""; };
Options parse(int argc,char **argv) {
    Options o;
    for(int i=1;i<argc;i++) { std::string s=argv[i]; if(s=="--help") { std::cout<<"--N --steps --max-iter --jacobi-check-every --warmup-steps --trial --alpha --r --tol --solver jacobi|cg --init gaussian|sine|zero --output PATH --dump-field PATH\n"; std::exit(0); }
        if(i+1>=argc) throw std::runtime_error("missing argument for "+s);
        std::string v=argv[++i];
        if(s=="--N") o.n=std::stoi(v); else if(s=="--steps") o.steps=std::stoi(v); else if(s=="--max-iter") o.max_iter=std::stoi(v); else if(s=="--jacobi-check-every") o.check=std::stoi(v); else if(s=="--warmup-steps") o.warmup=std::stoi(v); else if(s=="--trial") o.trial=std::stoi(v); else if(s=="--alpha") o.alpha=std::stod(v); else if(s=="--r") o.r=std::stod(v); else if(s=="--tol") o.tol=std::stod(v); else if(s=="--solver") o.solver=v; else if(s=="--init") o.init=v; else if(s=="--output") o.output=v; else if(s=="--dump-field") o.dump=v; else throw std::runtime_error("unknown option "+s);
    }
    if(o.n<1 || o.steps<1 || o.max_iter<1 || o.check<1 || o.warmup<0 || !(o.alpha>0) || !(o.r>0) || !(o.tol>0) || !std::isfinite(o.alpha) || !std::isfinite(o.r) || !std::isfinite(o.tol) || (o.solver!="cg" && o.solver!="jacobi") || (o.init!="gaussian" && o.init!="sine" && o.init!="zero")) throw std::runtime_error("invalid arguments");
    return o;
}
void initialize(const Grid &g,const Options &o,Vec &x) {
    const double pi=std::acos(-1.0),h=1.0/(o.n+1);
    for(int i=1;i<=g.nx;i++) for(int j=1;j<=g.ny;j++) { double a=(g.ox+i)*h,b=(g.oy+j)*h, v=std::sin(pi*a)*std::sin(pi*b);
        if(o.init=="zero") v=0; else if(o.init=="gaussian") v*=0.25+1.1*std::exp(-(std::pow(a-.30,2)+std::pow(b-.35,2))/.012)+.65*std::exp(-(std::pow(a-.74,2)+std::pow(b-.63,2))/.006); x[g.at(i,j)]=v;
    }
}
Metrics solve(const Grid &g,const Options &o,const Vec &b,Vec &x) {
    Metrics m; Vec ax=g.field(),res=g.field(),p=g.field(),ap=g.field(),next=g.field(); x=b;
    MPI_Barrier(g.comm); double start=MPI_Wtime();
    double denom=std::max(std::sqrt(g.dot(b,b,m)),1e-30); g.apply(x,ax,m);
    double t=MPI_Wtime(); g.each([&](size_t k){res[k]=b[k]-ax[k]; p[k]=res[k];}); m.compute+=MPI_Wtime()-t;
    double rr=g.dot(res,res,m); m.checks++; m.residual=std::sqrt(rr)/denom;
    if(o.solver=="cg") {
        while(m.residual>o.tol && m.iterations<o.max_iter) {
            g.apply(p,ap,m); double pap=g.dot(p,ap,m); if(!(pap>0) || !std::isfinite(pap)) break;
            double a=rr/pap; t=MPI_Wtime(); g.each([&](size_t k){x[k]+=a*p[k]; res[k]-=a*ap[k];}); m.compute+=MPI_Wtime()-t;
            double newer=g.dot(res,res,m); m.iterations++; m.checks++; m.residual=std::sqrt(newer)/denom;
            if(!std::isfinite(m.residual) || m.residual<=o.tol) { rr=newer; break; }
            double beta=newer/rr; t=MPI_Wtime(); g.each([&](size_t k){p[k]=res[k]+beta*p[k];}); m.compute+=MPI_Wtime()-t; rr=newer;
        }
    } else {
        while(m.residual>o.tol && m.iterations<o.max_iter) {
            t=MPI_Wtime(); g.each([&](size_t k){next[k]=x[k]+res[k]/(1+4*g.r);}); x.swap(next); m.compute+=MPI_Wtime()-t; m.iterations++;
            g.apply(x,ax,m); t=MPI_Wtime(); g.each([&](size_t k){res[k]=b[k]-ax[k];}); m.compute+=MPI_Wtime()-t;
            if(m.iterations==1 || m.iterations%o.check==0 || m.iterations==o.max_iter) { rr=g.dot(res,res,m); m.checks++; m.residual=std::sqrt(rr)/denom; if(!std::isfinite(m.residual)) break; }
        }
    }
    m.total=MPI_Wtime()-start;
#ifdef HEAT_DIAGNOSTICS
    m.recursive_residual=m.residual;
#endif
    Metrics verification; g.apply(x,ax,verification); g.each([&](size_t k){res[k]=b[k]-ax[k];}); double true_rel=std::sqrt(g.dot(res,res,verification))/denom;
    m.ok=std::isfinite(true_rel) && true_rel<=o.tol; m.residual=true_rel; return m;
}
int main(int argc,char **argv) {
    MPI_Init(&argc,&argv); int worldrank=0; MPI_Comm_rank(MPI_COMM_WORLD,&worldrank);
    try {
        Options o=parse(argc,argv); Grid g(o.n,o.r); Vec x=g.field(),b=g.field(); initialize(g,o,x);
        for(int i=0;i<o.warmup;i++) { b=x; Metrics m=solve(g,o,b,x); if(!m.ok) throw std::runtime_error("warmup failed"); }
        initialize(g,o,x); std::vector<Metrics> steps; bool ok=true;
        for(int i=0;i<o.steps;i++) { b=x; Metrics m=solve(g,o,b,x); steps.push_back(m); if(!m.ok) {ok=false; break;} }
        char hostname[MPI_MAX_PROCESSOR_NAME]={}; int hostname_len=0; MPI_Get_processor_name(hostname,&hostname_len);
        std::vector<char> hosts(g.rank==0?static_cast<size_t>(g.size)*MPI_MAX_PROCESSOR_NAME:0);
        MPI_Gather(hostname,MPI_MAX_PROCESSOR_NAME,MPI_CHAR,hosts.data(),MPI_MAX_PROCESSOR_NAME,MPI_CHAR,0,g.comm);
        double sums[5]={},maxres=0; long iterations=0,halos=0,reductions=0,checks=0; std::vector<int> critical;
        for(const auto &m:steps) { struct {double value; int rank;} local{m.total,g.rank}, selected{}; MPI_Allreduce(&local,&selected,1,MPI_DOUBLE_INT,MPI_MAXLOC,g.comm); double chosen[5]={m.total,m.compute,m.halo,m.reduction,m.total-m.compute-m.halo-m.reduction}; MPI_Bcast(chosen,5,MPI_DOUBLE,selected.rank,g.comm); for(int k=0;k<5;k++) sums[k]+=chosen[k]; critical.push_back(selected.rank); iterations+=m.iterations; halos+=m.halos; reductions+=m.reductions; checks+=m.checks; maxres=std::max(maxres,m.residual); }
#ifdef HEAT_DIAGNOSTICS
        for(size_t s=0;s<steps.size();++s) { const auto &m=steps[s]; double local[6]={m.total,m.compute,m.halo,m.reduction,m.recursive_residual,m.residual}; std::vector<double> all(g.rank==0?6*g.size:0); MPI_Gather(local,6,MPI_DOUBLE,all.data(),6,MPI_DOUBLE,0,g.comm); if(g.rank==0) for(int rank=0;rank<g.size;rank++) { std::cerr<<std::setprecision(17)<<"DIAG "<<s<<' '<<rank; for(int k=0;k<6;k++) std::cerr<<' '<<all[6*rank+k]; std::cerr<<'\n'; } }
#endif
        if(!o.dump.empty()) { Vec local(static_cast<size_t>(o.n)*o.n,0),global; for(int i=1;i<=g.nx;i++) for(int j=1;j<=g.ny;j++) local[static_cast<size_t>(g.ox+i-1)*o.n+g.oy+j-1]=x[g.at(i,j)]; if(g.rank==0) global.resize(local.size()); MPI_Reduce(local.data(),g.rank==0?global.data():nullptr,static_cast<int>(local.size()),MPI_DOUBLE,MPI_SUM,0,g.comm); if(g.rank==0) { std::ofstream f(o.dump); if(!f) throw std::runtime_error("cannot write field"); f<<std::setprecision(17); for(int i=0;i<o.n;i++) {for(int j=0;j<o.n;j++) f<<(j?",":"")<<global[static_cast<size_t>(i)*o.n+j]; f<<'\n';} } }
        if(g.rank==0) { std::ostringstream out; out<<std::setprecision(17)<<"{\"status\":\""<<(ok?"ok":"nonconverged")<<"\",\"solver\":\""<<o.solver<<"\",\"init\":\""<<o.init<<"\",\"N\":"<<o.n<<",\"P\":"<<g.size<<",\"cart_dims\":["<<g.dims[0]<<','<<g.dims[1]<<"],\"alpha\":"<<o.alpha<<",\"r\":"<<o.r<<",\"h\":"<<1.0/(o.n+1)<<",\"dt\":"<<o.r/(o.alpha*(o.n+1.0)*(o.n+1.0))<<",\"tol\":"<<o.tol<<",\"max_iter\":"<<o.max_iter<<",\"jacobi_check_every\":"<<o.check<<",\"steps_requested\":"<<o.steps<<",\"steps_completed\":"<<steps.size()<<",\"warmup_steps\":"<<o.warmup<<",\"trial\":"<<o.trial<<",\"iteration_total\":"<<iterations<<",\"halo_count\":"<<halos<<",\"allreduce_count\":"<<reductions<<",\"residual_checks\":"<<checks<<",\"residual_rel_max\":"<<maxres<<",\"solve_total_s\":"<<sums[0]<<",\"compute_s\":"<<sums[1]<<",\"halo_s\":"<<sums[2]<<",\"reduction_s\":"<<sums[3]<<",\"other_s\":"<<sums[4]<<",\"critical_ranks\":["; for(size_t i=0;i<critical.size();i++) out<<(i?",":"")<<critical[i]; out<<"],\"hostname_by_rank\":["; for(int i=0;i<g.size;i++) out<<(i?",":"")<<'"'<<hosts.data()+static_cast<size_t>(i)*MPI_MAX_PROCESSOR_NAME<<'"'; out<<"]}"; if(o.output.empty()) std::cout<<out.str()<<'\n'; else {std::ofstream f(o.output); if(!f) throw std::runtime_error("cannot write output"); f<<out.str()<<'\n';} }
        MPI_Comm_free(&g.comm); MPI_Finalize(); return ok?0:2;
    } catch(const std::exception &e) { if(worldrank==0) std::cerr<<"error: "<<e.what()<<'\n'; MPI_Abort(MPI_COMM_WORLD,1); return 1; }
}
