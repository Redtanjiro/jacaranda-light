import xml.etree.ElementTree as ET, pickle
nodes={};ways=[];rels=[]
for ev,el in ET.iterparse('sydney.osm',events=('end',)):
    t=el.tag
    if t=='node': nodes[int(el.get('id'))]=(float(el.get('lon')),float(el.get('lat'))); el.clear()
    elif t=='way':
        tags={x.get('k'):x.get('v') for x in el.findall('tag')}
        keep=('highway' in tags) or tags.get('natural') in('coastline','water','wood','beach','scrub') or tags.get('leisure') in('park','golf_course','pitch','nature_reserve','garden') or tags.get('landuse') in('grass','recreation_ground','cemetery','forest') or tags.get('waterway') in('riverbank',) or tags.get('railway')=='rail' or tags.get('aeroway') in('runway',)
        if keep: ways.append((int(el.get('id')),[int(n.get('ref')) for n in el.findall('nd')],tags))
        el.clear()
    elif t=='relation':
        tags={x.get('k'):x.get('v') for x in el.findall('tag')}
        if tags.get('type')=='multipolygon' and (tags.get('leisure') in('park','golf_course','nature_reserve') or tags.get('natural')=='water'):
            rels.append(([(int(m.get('ref')),m.get('role')) for m in el.findall('member') if m.get('type')=='way'],tags))
        el.clear()
pickle.dump((nodes,ways,rels),open('osm.pkl','wb'))
from collections import Counter
print(len(nodes),len(ways),len(rels));print(Counter(w[2].get('highway') for w in ways if 'highway' in w[2]).most_common(20))
