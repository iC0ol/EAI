import mujoco
import numpy as np
from m_direction.io import array_hash


class PhysicalObserver:
    def __init__(self,env):
        self.raw=env.env;self.model=self.raw.sim.model._model;self.data=mujoco.MjData(self.model)
        r=self.raw.robots[0]
        self.nut=self.raw.obj_body_id['SquareNut'];self.peg=self.raw.peg1_body_id
        self.site=r.eef_site_id['right'];self.body=self.raw.sim.model.body_name2id(r.robot_model.eef_name['right'])
        self.grip=r._ref_gripper_joint_pos_indexes['right']
    def from_state(self,s):
        m,d=self.model,self.data;d.time=s[0];d.qpos[:]=s[1:1+m.nq];d.qvel[:]=s[1+m.nq:1+m.nq+m.nv]
        mujoco.mj_kinematics(m,d)
        return np.r_[d.xpos[self.nut],d.xquat[self.nut][[1,2,3,0]],d.site_xpos[self.site],d.xquat[self.body][[1,2,3,0]],d.qpos[self.grip]].copy()
    def live(self):
        sim=self.raw.sim
        before=[array_hash(x.copy()) for x in [sim.data.qpos,sim.data.qvel,sim.data.qacc_warmstart,sim.data.ctrl]]
        out=self.from_state(sim.get_state().flatten())
        assert before==[array_hash(x.copy()) for x in [sim.data.qpos,sim.data.qvel,sim.data.qacc_warmstart,sim.data.ctrl]]
        return out
    def frames(self):
        self.live()
        return self.data.xmat[self.nut].reshape(3,3).copy(),self.data.xmat[self.peg].reshape(3,3).copy(),self.data.xpos[self.peg].copy()


def contact_frame(raw,peg_rotation,cfg):
    m,d=raw.sim.model._model,raw.sim.data._data
    contacts=[];cov=np.zeros((3,3));total=0.
    for i in range(d.ncon):
        c=d.contact[i]
        names=[mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_GEOM,int(g)) if g>=0 else '' for g in c.geom]
        if not any('SquareNut' in (n or '') for n in names):continue
        other=[n or '' for n in names if 'SquareNut' not in (n or '')]
        if not any('gripper0_right_' in n or 'peg' in n for n in other):continue
        f=np.zeros(6);mujoco.mj_contactForce(m,d,i,f)
        n=c.frame[:3].copy();weight=max(0.,float(f[0]));cov+=weight*np.outer(n,n);total+=weight
        contacts.append({'geoms':names,'ids':c.geom.tolist(),'point':c.pos.tolist(),'normal':n.tolist(),'force_torque':f.tolist(),'efc_address':int(c.efc_address)})
    info={'ncon':int(d.ncon),'force_sum_N':total,'contacts':contacts,'solver_geometry_time_note':'last native physics solve; data.time is after its integration, no extra forward'}
    if total<cfg['contact_normal_min_sum_force_N']:return None,{**info,'available':False,'reason':'insufficient relevant contact force'}
    eig,v=np.linalg.eigh(cov/total);n=v[:,-1]
    info['normal_eigenvalues']=eig.tolist()
    if eig[-1]<cfg['contact_normal_min_leading_fraction'] or eig[-1]-eig[-2]<cfg['contact_normal_min_eigengap']:
        return None,{**info,'available':False,'reason':'ambiguous contact-normal second moment'}
    for reference in [peg_rotation[:,2],peg_rotation[:,1],peg_rotation[:,0]]:
        dot=n@reference
        if abs(dot)>1e-9:n=n*np.sign(dot);break
    tangent=peg_rotation[:,0]-n*(n@peg_rotation[:,0])
    if np.linalg.norm(tangent)<1e-6:tangent=peg_rotation[:,1]-n*(n@peg_rotation[:,1])
    tangent/=np.linalg.norm(tangent)
    frame=np.column_stack([tangent,np.cross(n,tangent),n])
    np.testing.assert_allclose(frame.T@frame,np.eye(3),atol=1e-12,rtol=0)
    return frame,{**info,'available':True,'reason':''}
