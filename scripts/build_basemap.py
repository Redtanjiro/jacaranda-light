import pickle,json,math
from shapely.geometry import LineString,Polygon,box,Point,MultiPolygon
from shapely.ops import linemerge,unary_union,polygonize
nodes,ways,rels=pickle.load(open('osm.pkl','rb'))
B=(151.0793,-34.0049,151.2961,-33.8226); bb=box(*B)
def coords(w): return [nodes[n] for n in w[1] if n in nodes]
# ---- land from coastline
coast=[LineString(coords(w)) for w in ways if w[2].get('natural')=='coastline' and len(coords(w))>1]
merged=linemerge(coast); lines0=list(merged.geoms) if hasattr(merged,'geoms') else [merged]
def ext(p):
    x,y=p;d={'w':x-B[0],'e':B[2]-x,'s':y-B[1],'n':B[3]-y};k=min(d,key=d.get)
    return {'w':(B[0]-0.001,y),'e':(B[2]+0.001,y),'s':(x,B[1]-0.001),'n':(x,B[3]+0.001)}[k]
lines=[]
for l in lines0:
    c=list(l.coords)
    if not l.is_ring: c=[ext(c[0])]+c+[ext(c[-1])]
    lines.append(LineString(c))
clipped=unary_union([l.intersection(bb) for l in lines]+[bb.exterior])
faces=list(polygonize(clipped))
segs=[]
for l in lines:
    c=list(l.coords)
    for a,b in zip(c,c[1:]): segs.append((a,b))
def is_land(poly):
    p=poly.representative_point();best=None;bd=1e9
    for a,b in segs:
        s=LineString([a,b]);d=s.distance(p)
        if d<bd: bd=d;best=(a,b)
    a,b=best;cr=(b[0]-a[0])*(p.y-a[1])-(b[1]-a[1])*(p.x-a[0]);return cr>0
land=[f for f in faces if is_land(f)]
def q(x,y): return [round((x-151)*1e5),round((y+34)*1e5)]
print('faces',len(faces),'land',len(land),[round(f.area*1e4,2) for f in land][:10])
# islands: closed coastline rings fully inside are polygons themselves (polygonize handles)
import pickle as _p
subs=[(p,g) for p,g in _p.load(open('subs.pkl','rb')) if str(p.get('enddate','')).startswith('3000')]
landU=unary_union([g.buffer(0) for p,g in subs]).buffer(0.00002).buffer(-0.00002).simplify(0.00003)
SUBS=[]
for p,g in subs:
    if g.area<2e-6: continue
    c=g.representative_point();SUBS.append([p['suburbname'].title(),*q(c.x,c.y),round(g.area*1e6)])
json.dump([[p['suburbname'].title(),g.simplify(0.0001).wkt] for p,g in subs],open('subs_wkt.json','w'))
def q(x,y): return [round((x-151)*1e5),round((y+34)*1e5)]
def enc(cs):
    out=[];px=py=0
    for x,y in cs:
        X,Y=q(x,y);out+= [X-px,Y-py];px,py=X,Y
    return out
def polys(g):
    gs=list(g.geoms) if hasattr(g,'geoms') else [g];res=[]
    for p in gs:
        if p.area<2e-8: continue
        res.append([enc(p.exterior.coords)]+[enc(i.coords) for i in p.interiors])
    return res
LAND=polys(landU)
# ---- greens & water polygons
green=[];water=[]
for w in ways:
    t=w[2];c=coords(w)
    if len(c)<4 or c[0]!=c[-1]: continue
    g=t.get('leisure') in('park','golf_course','nature_reserve','garden','pitch') or t.get('landuse') in('grass','recreation_ground','cemetery','forest') or t.get('natural') in('wood','scrub')
    wa=t.get('natural')=='water' or t.get('waterway')=='riverbank'
    if g or wa:
        try:P=Polygon(c).buffer(0)
        except: continue
        if P.area<4e-8: continue
        (green if g else water).append(P)
wayd={w[0]:w for w in ways}
for mem,t in rels:
    outer=[LineString(coords(wayd[m])) for m,r in mem if r=='outer' and m in wayd and len(coords(wayd[m]))>1]
    if not outer: continue
    try:
        ps=list(polygonize(linemerge(outer)))
    except: continue
    for P in ps:
        if P.area<4e-8: continue
        (water if t.get('natural')=='water' else green).append(P)
G=polys(unary_union(green).intersection(landU).simplify(0.00003))
WA=polys(unary_union(water).simplify(0.00003))
# ---- roads
CLS={'motorway':0,'trunk':0,'motorway_link':0,'trunk_link':0,'primary':1,'primary_link':1,'secondary':2,'secondary_link':2,'tertiary':2,'tertiary_link':2,'residential':3,'unclassified':3,'living_street':3,'pedestrian':3}
roads=[[],[],[],[]]
for w in ways:
    h=w[2].get('highway')
    if h in CLS:
        c=coords(w)
        if len(c)<2: continue
        l=LineString(c).simplify(0.000025)
        roads[CLS[h]].append(enc(l.coords))
rail=[enc(LineString(coords(w)).simplify(0.00003).coords) for w in ways if w[2].get('railway')=='rail' and len(coords(w))>1 and not w[2].get('tunnel')]
out=dict(sub=SUBS,b=[q(B[0],B[1]),q(B[2],B[3])],land=LAND,green=G,water=WA,roads=roads,rail=rail)
s=json.dumps(out,separators=(',',':'));open('basemap.json','w').write(s)
print(len(s)/1e6,'MB',[len(r) for r in roads],len(G),len(WA),len(LAND))
