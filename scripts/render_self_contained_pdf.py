#!/usr/bin/env python3
"""Render the explanatory deck as a 16:9 PDF without opening a browser.

Uses the HTML's visible text and measured SVGs. The original decks are read-only.
"""
from pathlib import Path
from html.parser import HTMLParser
import html
import re
import xml.etree.ElementTree as ET
import fitz

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'slides/implicit-heat-self-contained.html'
TARGET=SOURCE.with_suffix('.pdf')
VOID={'br','img','meta','link','hr','input'}


class Node:
    def __init__(self,tag='',attrs=(),parent=None):
        self.tag=tag;self.attrs=dict(attrs);self.parent=parent;self.children=[]

    def all(self,tag=None,cls=None):
        out=[]
        for c in self.children:
            if isinstance(c,Node):
                if (tag is None or c.tag==tag) and (cls is None or cls in c.attrs.get('class','').split()):out.append(c)
                out+=c.all(tag,cls)
        return out

    def first(self,tag=None,cls=None):return self.all(tag,cls)[0]
    def text(self):return ''.join(c.text() if isinstance(c,Node) else c for c in self.children)
    def inner(self):return ''.join(c.outer() if isinstance(c,Node) else html.escape(c) for c in self.children)
    def outer(self):
        a=''.join(f' {k}="{html.escape(v or "",quote=True)}"' for k,v in self.attrs.items())
        return f'<{self.tag}{a}>'+('' if self.tag in VOID else self.inner()+f'</{self.tag}>')


class Parse(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.root=Node();self.current=self.root
    def handle_starttag(self,t,a):
        n=Node(t,a,self.current);self.current.children.append(n)
        if t not in VOID:self.current=n
    def handle_startendtag(self,t,a):self.current.children.append(Node(t,a,self.current))
    def handle_endtag(self,t):
        n=self.current
        while n.parent and n.tag!=t:n=n.parent
        if n.parent:self.current=n.parent
    def handle_data(self,s):self.current.children.append(s)


parser=Parse();parser.feed(SOURCE.read_text())
slides=parser.root.all('section',cls='slide')
assert len(slides)==19
DOC=fitz.open()
BG=(247/255,244/255,238/255)
INK=(36/255,35/255,33/255)
SECONDARY=(97/255,92/255,85/255)
ACCENT=(174/255,72/255,38/255)
BORDER=(216/255,212/255,205/255)
OVERLAY=[]


def plain(s):return re.sub(r'\s+',' ',s).strip()


def draw_html(page,rect,content,size=22,color='#615c55',label='body'):
    css=f'''body {{ margin:0; font-family:sans-serif; font-size:{size}px; line-height:1.35; color:{color}; }}
    p {{ margin:0 0 12px; }} h3 {{ font-size:{size+4}px; line-height:1.2; font-weight:bold; margin:0 0 14px; color:#242321; }}
    strong {{ font-weight:bold; color:#242321; }} ul {{ padding-left:24px; margin:12px 0 0; }}
    li {{ margin:0 0 7px; }} a {{ color:#242321; text-decoration:underline; }}
    .large-equation {{ font-size:34px; line-height:1.2; margin:12px 0; }}'''
    story=fitz.Story(html='<html><body>'+content+'</body></html>',user_css=css)
    more,filled=story.place(fitz.Rect(rect))
    if more:raise RuntimeError(f'Slide {len(DOC)} {label} does not fit {rect}: {filled}')
    # Story draws onto a temporary page, then the vector result is placed on ours.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'piece.pdf';writer=fitz.DocumentWriter(str(path))
        dev=writer.begin_page(fitz.Rect(0,0,1280,720));story.draw(dev);writer.end_page();writer.close()
        part=fitz.open(path);page.show_pdf_page(fitz.Rect(rect),part,0,clip=fitz.Rect(rect))
    return filled[3]


def svg(page,node,rect):
    root=ET.fromstring(node.outer())
    # HTMLParser lowercases attributes; SVG's viewBox is case-sensitive.
    if 'viewbox' in root.attrib:root.set('viewBox',root.attrib.pop('viewbox'))
    bounds=root.attrib['viewBox'].split()
    root.set('width',bounds[2]);root.set('height',bounds[3])
    is_chart='data-chart' in root.attrib.get('class','')
    def walk(el,parent_classes=()):
        tag=el.tag.rsplit('}',1)[-1];classes=el.attrib.get('class','').split()
        allc=tuple(parent_classes)+tuple(classes)
        if tag=='text':
            el.set('font-family','Helvetica');el.set('fill','#615c55');el.set('font-size','17')
            if 'end-label' in classes:
                el.set('font-size','19');el.set('fill','#ae4826' if 'cg' in classes else '#454842')
            if 'rank-label' in classes:
                el.set('font-size','24');el.set('fill','#242321')
            if 'stencil-text' in allc:
                el.set('font-size','23' if 'center-label' in classes else '28')
                el.set('text-anchor','middle');el.set('fill','#f7f4ee' if 'center-label' in classes else '#242321')
        if 'gridline' in classes or 'cellline' in classes:
            el.set('stroke','#d8d4cd');el.set('stroke-width','1')
        if 'threshold' in classes:
            el.set('stroke','#615c55');el.set('stroke-dasharray','6 6');el.set('stroke-width','1')
        if 'series' in classes or 'range' in classes:
            el.set('fill','none');el.set('stroke','#ae4826' if 'cg' in classes else '#454842')
            el.set('stroke-width','3' if 'series' in classes else '1.5')
        if 'point' in classes:
            el.set('fill','#f7f4ee');el.set('stroke','#ae4826' if 'cg' in classes else '#454842');el.set('stroke-width','2')
        if 'owned' in classes:
            el.set('fill','#ebe6dd');el.set('stroke','#d8d4cd')
        if 'halo-strip' in classes:
            el.set('fill','#ae4826');el.set('opacity','.65')
        if 'exchange-line' in classes:el.set('stroke','#ae4826');el.set('stroke-width','3')
        if 'stencil-line' in classes:el.set('stroke','#d8d4cd');el.set('fill','none');el.set('stroke-width','2')
        if tag=='rect' and 'stencil-neighbor' in allc:el.set('fill','#ebe6dd');el.set('stroke','#d8d4cd')
        if 'stencil-center' in classes:el.set('fill','#ae4826')
        for child in el:walk(child,allc)
    walk(root)
    if is_chart:
        # Draw chart labels as PDF text to avoid SVG font clipping in some readers.
        box=fitz.Rect(rect);sw,sh=float(bounds[2]),float(bounds[3])
        scale=min(box.width/sw,box.height/sh)
        ox=box.x0+(box.width-sw*scale)/2;oy=box.y0+(box.height-sh*scale)/2
        for parent in root.iter():
            for text in list(parent):
                if text.tag.rsplit('}',1)[-1]!='text':continue
                value=''.join(text.itertext());size=float(text.attrib['font-size'])*scale
                x=ox+float(text.attrib['x'])*scale;y=oy+float(text.attrib['y'])*scale
                width=fitz.get_text_length(value,fontsize=size)
                anchor=text.attrib.get('text-anchor','start')
                if anchor=='end':x-=width
                elif anchor=='middle':x-=width/2
                color=text.attrib['fill'].lstrip('#')
                rgb=tuple(int(color[j:j+2],16)/255 for j in (0,2,4))
                OVERLAY.append(((x,y),value,size,rgb))
                parent.remove(text)
    s=ET.tostring(root,encoding='utf-8')
    image=fitz.open(stream=s,filetype='svg');vector=fitz.open(stream=image.convert_to_pdf(),filetype='pdf')
    page.show_pdf_page(fitz.Rect(rect),vector,0)


def draw_table(page,node,cols,top=224,rowheight=54,size=22):
    rows=node.all('tr');x0=64
    for r,row in enumerate(rows):
        cells=[c for c in row.children if isinstance(c,Node) and c.tag in ('td','th')]
        x=x0;rh=46 if r==0 else rowheight
        for c,width in zip(cells,cols):
            content=('<strong>'+c.inner()+'</strong>') if r==0 else c.inner()
            draw_html(page,(x+8,top+9,x+width-8,top+rh-3),content,19 if r==0 else size,label='table cell')
            x+=width
        top+=rh;page.draw_line((64,top),(1216,top),color=BORDER,width=1)
    return top


def draw_equation(page,formula,rect):
    import io
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.mathtext import math_to_image
    from matplotlib.font_manager import FontProperties
    image=io.BytesIO()
    math_to_image('$'+formula+'$',image,prop=FontProperties(size=38),format='svg',color='#242321')
    equation_svg=re.sub(rb'<g id="patch_1">.*?</g>',b'',image.getvalue(),flags=re.S)
    source=fitz.open(stream=equation_svg,filetype='svg')
    vector=fitz.open(stream=source.convert_to_pdf(),filetype='pdf')
    page.show_pdf_page(fitz.Rect(rect),vector,0)


for index,section in enumerate(slides,1):
    OVERLAY=[]
    page=DOC.new_page(width=1280,height=720)
    page.draw_rect(page.rect,color=None,fill=BG)
    page.insert_text((64,52),'+',fontname='helv',fontsize=24,color=ACCENT)
    page.insert_text((92,52),'CS598 / MPI heat diffusion',fontname='helv',fontsize=16,color=SECONDARY)
    chapter=section.first(cls='chapter').text()
    page.insert_text((1216-fitz.get_text_length(chapter,fontsize=16),52),chapter,fontsize=16,color=SECONDARY)
    title=section.first('h1' if index==1 else 'h2')
    if index==1:
        draw_html(page,(64,116,712,280),'<h3 style="font-size:72px;font-weight:bold;line-height:1.05">'+title.inner()+'</h3>',72,'#242321','cover title')
    else:
        draw_html(page,(64,94,1216,154),'<strong>'+title.inner()+'</strong>',44,'#242321','title')
        draw_html(page,(64,166,1216,216),section.first(cls='context-line').inner(),19,label='context')
    body=section.first(cls='slide-body')
    if index==1:
        cover=body.first(cls='explained-cover')
        left=next(c for c in cover.children if isinstance(c,Node) and c.tag=='div')
        desc=left.first(cls='cover-description')
        end=draw_html(page,(64,292,704,406),desc.outer(),22,label='cover introduction')
        question=left.first(cls='cover-question')
        page.draw_line((64,418),(64,538),color=ACCENT,width=3)
        draw_html(page,(84,412,700,544),question.inner(),22,label='research question')
        draw_html(page,(64,555,700,600),left.first(cls='cover-authors').inner(),15,label='authors')
        figure=cover.first('figure');svg(page,figure.first('svg'),(792,116,1192,516))
        draw_html(page,(792,532,1216,596),figure.first('figcaption').inner(),16,label='field caption')
    elif 'chart-slide' in section.attrs.get('class',''):
        svg(page,body.first('svg'),(64,218,1216,478))
        articles=body.first(cls='interpretation').all('article')
        for a,x in zip(articles,(64,664)):
            draw_html(page,(x,490,x+552,596),a.inner(),20,label='chart interpretation')
    elif 'parameter-slide' in section.attrs.get('class',''):
        articles=body.first(cls='parameter-top').all('article')
        for a,x in zip(articles,(64,664)):
            draw_html(page,(x,224,x+552,268),a.first('h3').outer(),22,label='parameter heading')
            draw_html(page,(x,360,x+552,440),a.first('p').outer(),20,label='symbol definitions')
        draw_equation(page,r'h=\frac{1}{N+1}',(200,268,480,346))
        draw_equation(page,r'r=\frac{\alpha\Delta t}{h^2}',(800,268,1080,346))
        for a,x in zip(body.first(cls='parameter-insights').all('article'),(64,664)):
            draw_html(page,(x,452,x+552,596),a.inner(),20,label='fixed-r interpretation')
    elif 'correctness-slide' in section.attrs.get('class',''):
        for i,a in enumerate(body.first(cls='correctness-checks').all('article')):
            y=224+i*124
            page.insert_text((64,y+24),f'{i+1:02d}',fontname='cour',fontsize=18,color=ACCENT)
            detail=next(c for c in a.children if isinstance(c,Node) and c.tag=='div')
            draw_html(page,(120,y,1216,y+116),detail.inner(),21,label='correctness check')
            if i<2:page.draw_line((120,y+112),(1216,y+112),color=BORDER,width=1)
    elif index in (5,11,12,17):
        widths={5:[240,824,88],11:[600,276,276],12:[240,456,456],17:[160,248,248,248,248]}[index]
        end=draw_table(page,body.first('table'),widths,rowheight=72 if index==5 else 42 if index==12 else 54,size=20 if index==5 else 22)
        if index==5:
            count=body.first(cls='experiment-count')
            draw_html(page,(64,end+20,616,600),count.first('strong').outer(),26,'#ae4826','run count')
            draw_html(page,(664,end+20,1216,600),count.first('p').inner(),18,label='group explanation')
        else:
            for a,x in zip(body.first(cls='compact-insight').all('article'),(64,664)):
                draw_html(page,(x,end+20,x+552,596),a.inner(),21,label='table interpretation')
    elif index==2:
        cols=body.first(cls='two-col').all('article')
        draw_html(page,(64,224,616,582),cols[0].inner(),21,label='model explanation')
        svg(page,cols[1].first('svg'),(716,224,1116,466))
        draw_html(page,(664,478,1216,590),cols[1].first('p').inner(),21,label='stencil explanation')
    elif index==3:
        figure=body.first('figure')
        svg(page,figure.first('svg'),(64,224,616,496))
        draw_html(page,(64,508,616,584),figure.first('figcaption').inner(),18,label='halo caption')
        draw_html(page,(664,224,1216,590),body.first('article').inner(),21,label='MPI explanation')
    elif index in (4,6):
        articles=body.first(cls='two-col').all('article')
        for a,x in zip(articles,(64,664)):
            draw_html(page,(x,224,x+552,510 if index in (4,6) else 590),a.inner(),20 if index in (4,6) else 21,label='explanation column')
        strips=body.all(cls='accuracy-strip')
        if strips:draw_html(page,(64,526,1216,592),strips[0].inner(),19,label='accuracy and placement')
    elif index==19:
        points=body.first(cls='conclusion-points').all('article')
        y=224
        for i,a in enumerate(points,1):
            page.insert_text((64,y+22),f'{i:02d}',fontname='cour',fontsize=18,color=ACCENT)
            draw_html(page,(108,y,700,y+116),a.first('h3').outer()+a.first('p').outer(),20,label='conclusion')
            y+=120
        panel=body.first(cls='reproduction-panel')
        panel_html=panel.inner()
        links=panel.first(cls='source-links')
        panel_html=panel_html.replace(links.outer(),''.join('<p>'+a.outer()+'</p>' for a in links.all('a')))
        draw_html(page,(780,224,1216,592),panel_html,20,label='reproduction')
    takeaway=section.first(cls='slide-takeaway').inner()
    draw_html(page,(64,610,1216,654),takeaway,16 if 'chart-slide' in section.attrs.get('class','') else 18,label='takeaway')
    page.draw_line((64,600),(1216,600),color=BORDER,width=1)
    page.draw_line((64,662),(1216,662),color=BORDER,width=1)
    page.insert_text((64,690),'Extended study 12312735 · Jacobi and CG · Self-contained edition',fontsize=14,color=SECONDARY)
    counter=f'{index:02d} / {len(slides)}'
    page.insert_text((1216-fitz.get_text_length(counter,fontsize=14),690),counter,fontsize=14,color=SECONDARY)
    for point,value,size,color in OVERLAY:
        page.insert_text(point,value,fontsize=size,color=color)

# Match the original deck's physical page dimensions, retaining vector text/charts.
final=fitz.open()
for i in range(len(DOC)):
    p=final.new_page(width=960,height=540)
    p.show_pdf_page(p.rect,DOC,i)
final.set_metadata({'title':'Implicit heat diffusion: self-contained presentation',
                    'author':'Srikar Palani, Suprathik Vinayakula',
                    'subject':'Created with Visualize by careerhackeralex (MIT); design follows Unslop by Damir Sokolovsky (CC BY 4.0). https://github.com/careerhackeralex/visualize https://github.com/heydamir/unslop'})
final.save(TARGET,garbage=4,deflate=True)
print(f'Created {TARGET.name}: {len(final)} self-contained landscape pages.')
