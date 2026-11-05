"""Plots saved data only; no experiment or model execution."""
from pathlib import Path
import json,csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parents[1]
def read(n):return json.loads((P/n).read_text())
a=read('expert_result.json')['rollouts'];b=read('policy_result.json')['rollouts'];fig,ax=plt.subplots(4,2,figsize=(10.5,10),sharex=True,layout='constrained')
for root in range(4):
 groups=[(next(x for x in a if x['root']==root),'Expert','#167e80')]+[(next(x for x in b if x['root']==root and x['condition']==c),label,color) for c,label,color in [('train','Policy / train camera','#c94d3d'),('dev','Policy / dev camera','#cf8b2c')]]
 for r,label,color in groups:
  tr=[json.loads(x) for x in (P/r['trajectory']).read_text().splitlines()];dist=[float(np.linalg.norm(np.asarray(r['initial_EEF'])-r['initial_cube']))]+[x['distance_m'] for x in tr];height=[r['initial_cube'][2]]+[x['cube_position'][2] for x in tr]
  t=np.arange(len(dist));ax[root,0].plot(t,np.asarray(dist)*100,color=color,label=label,linewidth=1.7);ax[root,1].plot(t,np.asarray(height)*100,color=color,label=label,linewidth=1.7)
 ax[root,0].axhline(5,color='#525252',ls=':',lw=1,label='Reach threshold' if root==0 else None);ax[root,1].axhline(84,color='#525252',ls=':',lw=1)
 ax[root,0].set_ylabel(f'Root {root}\nDistance (cm)');ax[root,1].set_ylabel('Cube height (cm)')
 for aa in ax[root]:aa.grid(alpha=.2);aa.set_xlim(0,150)
ax[0,0].set_title('Actual EEF–cube distance');ax[0,1].set_title('Actual cube height (lift threshold: 84 cm)');ax[0,0].legend(fontsize=8,loc='upper right');ax[-1,0].set_xlabel('Environment step');ax[-1,1].set_xlabel('Environment step');fig.suptitle('Matched expert controls succeed; frozen policy does not reach the cube\nFour fixed substitute physical roots; paired training and development cameras',fontsize=12)
fig.savefig(P/'figures/expert_policy_behavior.png',dpi=180);fig.savefig(P/'figures/expert_policy_behavior.svg');plt.close(fig)
with (P/'artifacts/behavior_by_root.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['root','condition','steps','success','reach','grasp','min_EEF_cube_m','max_cube_height_m','initial_EEF_x','initial_EEF_y','initial_EEF_z','final_EEF_x','final_EEF_y','final_EEF_z'])
 for r in a+b:w.writerow([r['root'],r.get('condition','expert'),r['steps'],r['success'],r['reach'],r['grasp'],r['minimum_EEF_cube_distance_m'],r['maximum_cube_height_m'],*r['initial_EEF'],*r['final_EEF']])
print('Scientific behavior plots and descriptive raw metric CSV saved')
