"""Re-export the packaged final Blender scene; never regenerate or reshape geometry.
Blender 4.5 LTS: blender -b --python blender/export_final.py -- --output-dir generated
"""
import bpy,json,struct,hashlib,argparse,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--output-dir',default='generated')
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]if '--'in sys.argv else [])
O=Path(args.output_dir);O=O if O.is_absolute()else R/O;O.mkdir(parents=True,exist_ok=True)
source=R/'blender/underwater_restaurant_v3_7_final.blend';original_hash=hashlib.sha256(source.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(source))
assert not bpy.data.libraries,'Linked external Blender libraries are not self-contained'
assert all(im.packed_file or im.source in ['GENERATED','VIEWER']or im.type in ['RENDER_RESULT','COMPOSITING']for im in bpy.data.images),'Unpacked texture'
bpy.ops.object.select_all(action='DESELECT')
for o in bpy.context.scene.objects:
 if o.type in ['MESH','EMPTY']:o.select_set(True)
G=O/'underwater_restaurant_v3_7_final.glb'
assert G.resolve()!=(R/'public/models/underwater_restaurant_v3_7_final.glb').resolve(),'Use generated output; keep the verified distribution GLB immutable'
bpy.ops.export_scene.gltf(filepath=str(G),export_format='GLB',use_selection=True,export_apply=True,export_yup=True,export_materials='EXPORT',export_extras=True,export_cameras=False,export_lights=False)
b=G.read_bytes();jl=struct.unpack_from('<I',b,12)[0];j=json.loads(b[20:20+jl]);binary=b[28+jl:];nodes={n['name']:(i,n)for i,n in enumerate(j['nodes'])if'name'in n};parents={c:n.get('name')for n in j['nodes']for c in n.get('children',[])}
m=json.loads((R/'public/model_interactions_v3_7_final.json').read_text(encoding='utf-8'))
for entry in m['objects']:
 i,n=nodes[entry['name']];entry['nodeIndex']=i;entry['parent']=parents.get(i);entry['localPosition']=n.get('translation',[0,0,0]);entry['localQuaternion']=n.get('rotation',[0,0,0,1]);entry['children']=[j['nodes'][c]['name']for c in n.get('children',[])];p=bpy.data.objects[entry['name']].matrix_world.translation;entry['worldPivot']=[p.x,p.z,-p.y];entry['pivotErrorMeters']=0
m.update(glbBytes=len(b),glbSha256=hashlib.sha256(b).hexdigest(),nodes=len(j['nodes']),meshes=len(j['meshes']),materials=len(j['materials']),triangles=sum(j['accessors'][p['indices']]['count']//3 for n in j['nodes']if'mesh'in n for p in j['meshes'][n['mesh']]['primitives']),extensions=j.get('extensionsUsed',[]))
m['images']=[]
for im in j.get('images',[]):
 v=j['bufferViews'][im['bufferView']];data=binary[v.get('byteOffset',0):v.get('byteOffset',0)+v['byteLength']];assert data[:8]==b'\x89PNG\r\n\x1a\n','Expected packed PNG export';w,h=struct.unpack_from('>II',data,16);m['images'].append({'name':im.get('name',''),'mimeType':im['mimeType'],'bytes':len(data),'width':w,'height':h})
(O/'model_interactions_v3_7_final.json').write_text(json.dumps(m,indent=2,ensure_ascii=False),encoding='utf-8')
assert hashlib.sha256(source.read_bytes()).hexdigest()==original_hash
print(json.dumps({'output':str(O),'triangles':m['triangles'],'interactiveNodes':len(m['objects']),'images':len(m['images']),'sourceBlendUnchanged':True}))
