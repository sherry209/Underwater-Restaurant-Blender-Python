"""V3.7 final: edit saved render scene only; all pivots and unrelated meshes immutable."""
import bpy,bmesh,math,json,hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];O=R/'blender/v3_7_final';O.mkdir(exist_ok=True)
SOURCE=R/'blender/v3_7_render/underwater_restaurant_v3_7_render.blend'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));s=bpy.context.scene

def signature(o):
 d={'matrix':[list(r)for r in o.matrix_world],'parent':o.parent.name if o.parent else None,'type':o.type}
 if o.type=='MESH':d.update(mesh=hashlib.sha256(repr(([tuple(v.co)for v in o.data.vertices],[tuple(p.vertices)for p in o.data.polygons],[[tuple(l.uv)for l in u.data]for u in o.data.uv_layers])).encode()).hexdigest(),materials=[m.name for m in o.data.materials])
 return d
before={o.name:signature(o)for o in s.objects};P=bpy.data.objects['V33_Private_Spatial_Root'].matrix_world.copy();PI=P.inverted()
def tree(names):
 vs=[];fs=[];dg=bpy.context.evaluated_depsgraph_get()
 for name in names:
  o=bpy.data.objects[name];e=o.evaluated_get(dg);m=e.to_mesh();n=len(vs);vs.extend(o.matrix_world@v.co for v in m.vertices);fs.extend(tuple(n+i for i in p.vertices)for p in m.polygons);e.to_mesh_clear()
 return BVHTree.FromPolygons(vs,fs,epsilon=0)
roof=tree(['Vault | PBR | low iron structural glazing','V32 Rear curved glazing transition','V32 Curved mineral canopy'])
roof_fallback=[]
def roof_z(x,y):
 h=roof.ray_cast(Vector((x,y,.7)),Vector((0,0,1)),10)
 edge=3.65+.48*math.sin(min(9,max(-9,y))*.4)
 if h[0] is not None and abs(x-edge)>.25:return h[0].z
 # At the metal-covered glass/canopy joint, continue neighboring actual inner
 # panel planes across tiny panel gaps. A ray must not jump to an upper bevel.
 hits=[]
 if h[0] is not None:hits.append(h[0].z)
 for dx,dy in [(-.015,0),(.015,0),(0,-.015),(0,.015),(-.035,0),(.035,0),(0,-.035),(0,.035)]:
  q,n,i,d=roof.ray_cast(Vector((x+dx,y+dy,.7)),Vector((0,0,1)),10)
  if q is not None and abs(n.z)>.5:hits.append(q.z-(n.x*(x-q.x)+n.y*(y-q.y))/n.z)
 assert hits,('No actual roof surface or covered panel joint',x,y)
 if h[0] is None:roof_fallback.append([x,y])
 return min(hits)

def uv(me):
 me.update();layer=me.uv_layers.active or me.uv_layers.new(name='UVMap')
 for p in me.polygons:
  axes=[i for i in range(3)if i!=max(range(3),key=lambda a:abs(p.normal[a]))]
  for i in p.loop_indices:
   v=me.vertices[me.loops[i].vertex_index].co;layer.data[i].uv=(v[axes[0]],v[axes[1]])
def normals(me):
 bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free();me.update()
def replace(o,vs,fs):
 old=o.data;me=bpy.data.meshes.new(o.name+' final fitted solid');me.from_pydata(vs,[],fs)
 for m in old.materials:me.materials.append(m)
 o.data=me;normals(me);uv(me)

def bar_roof_z(x,y):
 z=roof_z(x,y)
 edge=3.65+.48*math.sin(min(9,max(-9,y))*.4)
 d=x-edge
 # Let the backing meet the retained 150mm-wide metal crown joint from below.
 # A narrow 14mm-to-0 tapered relief prevents a top-face diagonal cutting through
 # the last laminated panel at the glass-to-canopy transition.
 if -.25<d<.4:
  cap=6.054 if d<=.18 else 6.054+.016*min(1,(d-.18)/.22)
  z=min(z,cap)
 return z

# Extend the existing curved private canopy itself, keeping its underside, reveal,
# entrance fascia and footprint. Its upper surface follows evaluated glazing/soffit.
o=bpy.data.objects['V35 Curved private roof canopy'];o.data=o.data.copy();inv=o.matrix_world.inverted();roof_changes=[]
# Refine only the small glass-side strip before fitting: long original fan triangles
# otherwise bridge across the crown and can poke through a panel between vertices.
bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-7)
for i in range(18):
 bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=1e-7,plane_co=(3.45+i*.05,0,0),plane_no=(1,0,0))
for i in range(37):
 faces=[f for f in bm.faces if max(v.co.x for v in f.verts)<4.31];edges=set(e for f in faces for e in f.edges);verts=set(v for f in faces for v in f.verts)
 bmesh.ops.bisect_plane(bm,geom=list(verts)+list(edges)+faces,dist=1e-7,plane_co=(0,-1.5+i*.1,0),plane_no=(0,1,0))
boundary=[e for e in bm.edges if e.is_boundary]
if boundary:bmesh.ops.holes_fill(bm,edges=boundary,sides=0)
bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(o.data);bm.free();o.data.update()
for v in o.data.vertices:
 p=o.matrix_world@v.co
 if p.z<=5.475:continue
 old=p.z;target=bar_roof_z(p.x,p.y)-.00075;weight=max(0,min(1,(old-5.475)/.130))
 p.z=old+(target-5.63)*weight;v.co=inv@p;roof_changes.append(target-5.63)
normals(o.data)

# Move the full east arc inward with C2 blending, retaining its original ends.
# The 3.45m aperture bay is tangent to both new arc wings, without recessed returns.
old=[]
for i in range(801):
 y=9-18*i/800;x=13.2*math.sqrt(1-(y/12.3)**2)
 # Original 22cm shell centre, inward normal to the ellipse.
 t=Vector((13.2*y/(12.3**2*math.sqrt(1-(y/12.3)**2)),-1,0)).normalized();n=Vector((t.y,-t.x,0))
 q=PI@(Vector((x,y,0))+.11*n);old.append(q)
old.sort(key=lambda q:q.x)
left,right=-1.70,1.75;flat=3.53

def quint(t):return t*t*t*(10-15*t+6*t*t)
def point(q):
 if q.x<left:t=(left-q.x)/(left-old[0].x)
 elif q.x>right:t=(q.x-right)/(old[-1].x-right)
 else:t=0
 w=quint(max(0,min(1,t)));return Vector((q.x,flat+w*(q.y-flat),0)),.26-.04*w
# Resample original smooth ellipse with exact tangent bay endpoints.
def interp(u):
 for a,b in zip(old,old[1:]):
  if a.x<=u<=b.x:return a.lerp(b,(u-a.x)/(b.x-a.x))
 raise ValueError(u)
vs=[];fs=[];paths=[]
for aa,bb in [(old[0].x,left+.002),(right-.002,old[-1].x)]:
 path=[]
 for i in range(241):
  u=aa+(bb-aa)*i/240;q,width=point(interp(u));path.append((q,width))
 base=len(vs)
 for i,(q,width)in enumerate(path):
  tangent=(path[min(i+1,len(path)-1)][0]-path[max(0,i-1)][0]).normalized();n=Vector((-tangent.y,tangent.x,0))
  for sign,z in [(-1,-.48),(1,-.48),(-1,5.59),(1,5.59)]:
   p=q+sign*width*.5*n;p.z=z;vs.append(tuple(P@p))
 for i in range(len(path)-1):
  a=base+4*i;b=a+4;fs.extend([(a,b,b+2,a+2),(a+1,a+3,b+3,b+1),(a+2,b+2,b+3,a+3),(a,a+1,b+1,b)])
 a=base+4*(len(path)-1);fs.extend([(base,base+2,base+3,base+1),(a,a+1,a+3,a+2)]);paths.append([list(P@q)for q,w in path])
o=bpy.data.objects['V32 Continuous curved east wall'];replace(o,vs,fs)
# Keep its original curved structural easing, now reduced at the aperture abutments.
for m in o.modifiers:
 if m.type=='BEVEL':m.width=.002
# Extend the actual existing perforated bay to ground and main ceiling. Inner
# circular boundary and its thickness/position stay byte-exact; only outer ring changes.
o=bpy.data.objects['V35 Private retained circular aperture backwall'];o.data=o.data.copy();inv=o.matrix_world.inverted()
for i,v in enumerate(o.data.vertices):
 if i%2==0:continue
 q=PI@(o.matrix_world@v.co);inner=PI@(o.matrix_world@o.data.vertices[i-1].co);dx=inner.x+.05;dz=inner.z-2.92
 tx=(right+.05)/dx if dx>1e-8 else (left+.05)/dx if dx<-1e-8 else 1e9
 tz=(5.59-2.92)/dz if dz>1e-8 else (-.48-2.92)/dz if dz<-1e-8 else 1e9
 factor=min(tx,tz);q.x=-.05+factor*dx;q.z=2.92+factor*dz;v.co=inv@(P@q)
normals(o.data);uv(o.data)
removed=['V37 Private exterior return left','V37 Private exterior return right']
for name in removed:bpy.data.objects.remove(bpy.data.objects[name],do_unlink=True)

# Fit the existing bar backing to the INNER surfaces of evaluated laminated panels.
# The old analytic ellipse reached the glass centre line (13-15mm penetration).
bar_changes={}
for name in ['V36 Continuous curved winewall','V36 Curved glass-end backing return']:
 o=bpy.data.objects[name];o.data=o.data.copy();inv=o.matrix_world.inverted();deltas=[]
 for v in o.data.vertices:
  p=o.matrix_world@v.co
  if p.z<.7:continue
  target=bar_roof_z(p.x,p.y)-.002;deltas.append(target-p.z);p.z=target;v.co=inv@p
 normals(o.data);bar_changes[name]={'min_delta_m':min(deltas),'max_delta_m':max(deltas),'top_vertices':len(deltas)}
for name in ['V36 Winewall ceiling bronze seam','V36 Glass junction continuous seal']:
 o=bpy.data.objects[name];o.data=o.data.copy();inv=o.matrix_world.inverted()
 for v in o.data.vertices:
  p=o.matrix_world@v.co;edge=3.65+.48*math.sin(min(9,max(-9,p.y))*.4)
  analytic=.12+5.95*math.sqrt(max(0,1-((edge-p.x)/13.65)**2)) if p.x<edge else 6.07
  p.z+=bar_roof_z(p.x,p.y)-.002-analytic;v.co=inv@p
 normals(o.data)
bpy.context.view_layer.update()
after={o.name:signature(o)for o in s.objects};changed=[n for n in after if before.get(n)!=after[n]]
allowed={'V35 Curved private roof canopy','V32 Continuous curved east wall','V35 Private retained circular aperture backwall',*bar_changes,'V36 Winewall ceiling bronze seam','V36 Glass junction continuous seal'}
assert set(changed)==allowed,changed
assert all(before[n]['matrix']==after[n]['matrix']for n in after)
report={'base':'v3_7_render','changed_objects':changed,'removed_objects':removed,'new_objects':[],'preserved_objects':len(after)-len(changed),'all_existing_transforms_preserved':True,'porthole_and_all_pivots_moved_m':0,'private_canopy_extension_m':[min(roof_changes),max(roof_changes)],'bar_fitting':bar_changes,'roof_joint_fallback_count':len(roof_fallback),'east_wall_paths':paths,'notes':['Existing private canopy volume extended to actual evaluated main ceiling, original underside retained.','Two full-height C2 east-wall wings meet the retained aperture bay tangentially; recessed returns removed.','Bar walls terminate 2mm below evaluated glass inner surface.']}
(O/'refinement-report.json').write_text(json.dumps(report,indent=2));(O/'preserved-objects.json').write_text(json.dumps({n:before[n]for n in after if n not in allowed},indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(O/'underwater_restaurant_v3_7_final.blend'))
bpy.ops.object.select_all(action='DESELECT')
for o in s.objects:
 if o.type in ['MESH','EMPTY']:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(O/'full-export.glb'),export_format='GLB',use_selection=True,export_apply=True,export_yup=True,export_materials='EXPORT',export_extras=True,export_cameras=False,export_lights=False)
print('FINAL_REFINEMENT',json.dumps({k:v for k,v in report.items()if k!='east_wall_paths'}))
