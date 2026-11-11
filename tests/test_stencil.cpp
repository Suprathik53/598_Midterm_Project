// Exercise the production stencil directly, including both Cartesian orientations.
#define main implicit_heat_program_main
#include "../src/main.cpp"
#undef main

static double value(int i, int j) { return 1.0 + 3.0*i + 0.25*j + 0.1*i*j; }

static bool check(int n, bool transpose) {
    Grid g(n, 2.0);
    if (transpose) {
        MPI_Comm_free(&g.comm);
        std::swap(g.dims[0], g.dims[1]);
        int periods[2] = {0, 0};
        MPI_Cart_create(MPI_COMM_WORLD, 2, g.dims, periods, 0, &g.comm);
        MPI_Comm_rank(g.comm, &g.rank);
        MPI_Cart_coords(g.comm, g.rank, 2, g.coord);
        MPI_Cart_shift(g.comm, 0, 1, &g.neighbors[0], &g.neighbors[1]);
        MPI_Cart_shift(g.comm, 1, 1, &g.neighbors[2], &g.neighbors[3]);
        g.nx=n/g.dims[0]+(g.coord[0]<n%g.dims[0]);
        g.ny=n/g.dims[1]+(g.coord[1]<n%g.dims[1]);
        g.ox=g.coord[0]*(n/g.dims[0])+std::min(g.coord[0],n%g.dims[0]);
        g.oy=g.coord[1]*(n/g.dims[1])+std::min(g.coord[1],n%g.dims[1]);
        g.stride=g.ny+2;
    }
    Vec x=g.field(), out=g.field();
    for (int i=1;i<=g.nx;i++) for (int j=1;j<=g.ny;j++)
        x[g.at(i,j)]=value(g.ox+i-1,g.oy+j-1);
    Metrics m;
    g.apply(x,out,m);
    double error=0;
    auto cell=[n](int i,int j) { return i<0 || j<0 || i>=n || j>=n ? 0.0 : value(i,j); };
    for (int i=1;i<=g.nx;i++) for (int j=1;j<=g.ny;j++) {
        int a=g.ox+i-1,b=g.oy+j-1;
        double expected=9*cell(a,b)-2*(cell(a-1,b)+cell(a+1,b)+cell(a,b-1)+cell(a,b+1));
        error=std::max(error,std::abs(out[g.at(i,j)]-expected));
    }
    double global=0;
    MPI_Allreduce(&error,&global,1,MPI_DOUBLE,MPI_MAX,g.comm);
    MPI_Comm_free(&g.comm);
    return global<1e-12;
}

int main(int argc,char **argv) {
    MPI_Init(&argc,&argv);
    int rank=0; MPI_Comm_rank(MPI_COMM_WORLD,&rank);
    bool normal=check(5,false), transposed=check(5,true);
    if (rank==0) std::cout << (normal && transposed ? "PASS" : "FAIL")
                          << " direct stencil and both Cartesian orientations\n";
    MPI_Finalize();
    return normal && transposed ? 0 : 1;
}
