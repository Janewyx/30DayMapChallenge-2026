"""Extract unchanged small bed grids and record their internal arithmetic consistency."""
from pathlib import Path
import zipfile,json
import rasterio
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'data/findelen_gries/bed_study_supplement.zip'
dest=source.parent/'bed_study_extracted';dest.mkdir(exist_ok=True)
with zipfile.ZipFile(source) as archive:
 for name in archive.namelist():
  if name.startswith('supplement_files/') and not name.endswith('/'):
   (dest/Path(name).name).write_bytes(archive.read(name))
results=[]
for glacier in ['fin','gries']:
 def read(kind):
  with rasterio.open(dest/f'{kind}_{glacier}2016.asc') as d:return d.read(1,masked=True)
 surface,bed,thickness=read('dhm'),read('bedrock'),read('ice_thickness')
 residual=(surface-bed-thickness).compressed()
 results.append(dict(glacier=glacier,common_valid_cells=int(residual.size),max_abs_surface_minus_bed_minus_thickness_m=float(abs(residual).max()),median_abs_residual_m=float(np.median(abs(residual))),bed_min_m=float(bed.min()),bed_max_m=float(bed.max()),max_thickness_m=float(thickness.max())))
(ROOT/'data/bed_consistency.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
