# R0：锁定源码与历史证据（0新仿真步）

官方run_trained_agent是reset→get_state→reset_to；给定示教XML/state的playback明确采用reset→reset_to。model路径reset_to内部还会reset并重建XML。外层reset是否修复物理偏离待P1检验。

offline extractor逐状态reset_to(states[t])并强制更新观测，在线step直接返回采样缓存。HDF5的绝对物体位置与free-joint qpos一致，但未存提取命令，不能证明该文件曾执行哪一个转换命令。

P0只保存state/obs/收到的前缀动作及末端hash；历史t38..52的接触、控制器目标及warmstart数值不可追溯，不能虚构。新P1/P2将补记录；源示教仍缺这些采集中间量。EEF位置来自site，EEF四元数沿用body，不能偷换成site quat。

## official_rollout: d_alignment_pilot/external/robomimic-7c66e7a41b5d9dcc905b1a68346bfee1b49b79c9/robomimic/scripts/run_trained_agent.py

```text
94:     assert isinstance(env, EnvBase)
95:     assert isinstance(policy, RolloutPolicy)
96:     assert not (render and (video_writer is not None))
97: 
98:     policy.start_episode()
99:     obs = env.reset()
100:     state_dict = env.get_state()
101: 
102:     # hack that is necessary for robosuite tasks for deterministic action playback
103:     obs = env.reset_to(state_dict)
104: 
```

## official_playback: d_alignment_pilot/external/robomimic-7c66e7a41b5d9dcc905b1a68346bfee1b49b79c9/robomimic/scripts/playback_dataset.py

```text
118:     video_count = 0
119:     assert not (render and write_video)
120: 
121:     # load the initial state
122:     env.reset()
123:     env.reset_to(initial_state)
124: 
125:     traj_len = states.shape[0]
126:     action_playback = (actions is not None)
127:     if action_playback:
128:         assert states.shape[0] == actions.shape[0]
129: 
130:     for i in range(traj_len):
131:         if action_playback:
132:             env.step(actions[i])
133:             if i < traj_len - 1:
134:                 # check whether the actions deterministically lead to the same recorded states
135:                 state_playback = env.get_state()["states"]
136:                 if not np.all(np.equal(states[i + 1], state_playback)):
137:                     err = np.linalg.norm(states[i + 1] - state_playback)
138:                     print("warning: playback diverged by {} at step {}".format(err, i))
```

## offline_extractor: d_alignment_pilot/external/robomimic-7c66e7a41b5d9dcc905b1a68346bfee1b49b79c9/robomimic/scripts/dataset_states_to_obs.py

```text
92:     obs = env.reset_to(initial_state)
93: 
94:     # maybe add in intrinsics and extrinsics for all cameras
95:     camera_info = None
96:     is_robosuite_env = EnvUtils.is_robosuite_env(env=env)
97:     if is_robosuite_env:
98:         camera_info = get_camera_info(
99:             env=env,
100:             camera_names=camera_names, 
101:             camera_height=camera_height, 
102:             camera_width=camera_width,
103:         )
104: 
105:     traj = dict(
106:         obs=[], 
107:         next_obs=[], 
108:         rewards=[], 
109:         dones=[], 
110:         actions=np.array(actions), 
111:         states=np.array(states), 
112:         initial_state_dict=initial_state,
113:     )
114:     traj_len = states.shape[0]
115:     # iteration variable @t is over "next obs" indices
116:     for t in range(1, traj_len + 1):
117: 
118:         # get next observation
119:         if t == traj_len:
120:             # play final action to get next observation for last timestep
121:             next_obs, _, _, _ = env.step(actions[t - 1])
122:         else:
123:             # reset to simulator state to get observation
124:             next_obs = env.reset_to({"states" : states[t]})
125: 
126:         # infer reward signal
127:         # note: our tasks use reward r(s'), reward AFTER transition, so this is
128:         #       the reward for the current timestep
129:         r = env.get_reward()
130: 
131:         # infer done signal
132:         done = False
133:         if (done_mode == 1) or (done_mode == 2):
134:             # done = 1 at end of trajectory
135:             done = done or (t == traj_len)
136:         if (done_mode == 0) or (done_mode == 2):
137:             # done = 1 when s' is task success state
138:             done = done or env.is_success()["task"]
139:         done = int(done)
140: 
141:         # collect transition
142:         traj["obs"].append(obs)
143:         traj["next_obs"].append(next_obs)
```

## wrapper: d_alignment_pilot/external/robomimic-7c66e7a41b5d9dcc905b1a68346bfee1b49b79c9/robomimic/envs/env_robosuite.py

```text
124:         Args:
125:             action (np.array): action to take
126: 
127:         Returns:
128:             observation (dict): new observation dictionary
129:             reward (float): reward for this step
130:             done (bool): whether the task is done
131:             info (dict): extra information
132:         """
133:         obs, r, done, info = self.env.step(action)
134:         obs = self.get_observation(obs)
135:         return obs, r, self.is_done(), info
136: 
137:     def reset(self, unset_ep_meta=True):
138:         """
139:         Reset environment.
140: 
141:         Args:
142:             unset_ep_meta (np.array): whether to reset any previously set episode metadata (otherwise
143:                 will continue to use previous episode metadata)
144:         
145:         Returns:
146:             observation (dict): initial observation dictionary.
147:         """
148:         if unset_ep_meta and self.is_v15_or_higher:
149:             # unset the ep meta to clear out any ep meta that was previously set
150:             # (this feature was set from robosuite v1.5 onwards)
151:             self.env.unset_ep_meta()
152:         di = self.env.reset()
153:         return self.get_observation(di)
154: 
155:     def reset_to(self, state):
156:         """
157:         Reset to a specific simulator state.
158: 
159:         Args:
160:             state (dict): current simulator state that contains one or more of:
161:                 - states (np.ndarray): initial state of the mujoco environment
162:                 - model (str): mujoco scene xml
163:         
164:         Returns:
165:             observation (dict): observation dictionary after setting the simulator state (only
166:                 if "states" is in @state)
167:         """
168:         should_ret = False
169:         if "model" in state:
170:             if state.get("ep_meta", None) is not None:
171:                 # set relevant episode information
172:                 ep_meta = json.loads(state["ep_meta"])
173:             else:
174:                 ep_meta = {}
175: 
176:             if self.is_v15_or_higher: # newer versions of robosuite have this feature
177:                 self.env.set_ep_meta(ep_meta)
178:             # this reset is necessary.
179:             # while the call to env.reset_from_xml_string does call reset,
180:             # that is only a "soft" reset that doesn't actually reload the model.
181:             self.reset(unset_ep_meta=False)
182:             robosuite_version_id = int(robosuite.__version__.split(".")[1])
183:             if robosuite_version_id <= 3:
184:                 from robosuite.utils.mjcf_utils import postprocess_model_xml
185:                 xml = postprocess_model_xml(state["model"])
186:             else:
187:                 # v1.4 and above use the class-based edit_model_xml function
188:                 xml = self.env.edit_model_xml(state["model"])
189:             self.env.reset_from_xml_string(xml)
190:             self.env.sim.reset()
191:             if not self._is_v1:
192:                 # hide teleop visualization after restoring from model
193:                 self.env.sim.model.site_rgba[self.env.eef_site_id] = np.array([0., 0., 0., 0.])
194:                 self.env.sim.model.site_rgba[self.env.eef_cylinder_id] = np.array([0., 0., 0., 0.])
195:         if "states" in state:
196:             self.env.sim.set_state_from_flattened(state["states"])
197:             self.env.sim.forward()
198:             should_ret = True
199: 
200:         if "goal" in state:
201:             self.set_goal(**state["goal"])
202:         if should_ret:
203:             # only return obs if we've done a forward call - otherwise the observations will be garbage
204:             return self.get_observation()
205:         return None
```

## base: d_alignment_pilot/external/robosuite-51cc01785bab80ffeed20da15e67d7dd4140e76a/robosuite/environments/base.py

```text
374:         Args:
375:             force (bool): If True, will force all the observables to update their internal values to the newest
376:                 value. This is useful if, e.g., you want to grab observations when directly setting simulation states
377:                 without actually stepping the simulation.
378:         """
379:         for observable in self._observables.values():
380:             observable.update(timestep=self.model_timestep, obs_cache=self._obs_cache, force=force)
381: 
382:     def _get_observations(self, force_update=False):
383:         """
384:         Grabs observations from the environment.
385:         Args:
386:             force_update (bool): If True, will force all the observables to update their internal values to the newest
387:                 value. This is useful if, e.g., you want to grab observations when directly setting simulation states
388:                 without actually stepping the simulation.
389:         Returns:
390:             OrderedDict: OrderedDict containing observations [(name_string, np.array), ...]
391:         """
392:         observations = OrderedDict()
393:         obs_by_modality = OrderedDict()
394: 
395:         # Force an update if requested
396:         if force_update:
397:             self._update_observables(force=True)
398: 
399:         # Loop through all observables and grab their current observation
400:         for obs_name, observable in self._observables.items():
401:             if observable.is_enabled() and observable.is_active():
402:                 obs = observable.obs
403:                 observations[obs_name] = obs
404:                 modality = observable.modality + "-state"
405:                 if modality not in obs_by_modality:
406:                     obs_by_modality[modality] = []
407:                 # Make sure all observations are numpy arrays so we can concatenate them
408:                 array_obs = [obs] if type(obs) in {int, float} or not obs.shape else obs
409:                 obs_by_modality[modality].append(np.array(array_obs))
410: 
411:         # Add in modality observations
412:         for modality, obs in obs_by_modality.items():
413:             # To save memory, we only concatenate the image observations if explicitly requested
414:             if modality == "image-state" and not macros.CONCATENATE_IMAGES:
415:                 continue
416:             observations[modality] = np.concatenate(obs, axis=-1)
417: 
418:         return observations
419: 
```

## observables: d_alignment_pilot/external/robosuite-51cc01785bab80ffeed20da15e67d7dd4140e76a/robosuite/utils/observables.py

```text
214:     def update(self, timestep, obs_cache, force=False):
215:         """
216:         Updates internal values for this observable, if enabled.
217: 
218:         Args:
219:             timestep (float): Amount of simulation time (in sec) that has passed since last call.
220:             obs_cache (dict): Observation cache mapping observable names to pre-computed values to pass to sensor. This
221:                 will be updated in-place during this call.
222:             force (bool): If True, will force the observable to update its internal value to the newest value.
223:         """
224:         if self._enabled:
225:             # Increment internal time counter
226:             self._time_since_last_sample += timestep
227: 
228:             # If the delayed sampling time has been passed and we haven't sampled yet for this sampling period,
229:             # we should grab a new measurement
230:             if (
231:                 not self._sampled and self._sampling_timestep - self._current_delay >= self._time_since_last_sample
232:             ) or force:
233:                 # Get newest raw value, corrupt it, filter it, and set it as our current observed value
234:                 obs = np.array(self._filter(self._corrupter(self._sensor(obs_cache))))
235:                 self._current_observed_value = obs[0] if len(obs.shape) == 1 and obs.shape[0] == 1 else obs
236:                 # Update cache entry as well
237:                 obs_cache[self.name] = np.array(self._current_observed_value)
238:                 # Toggle sampled and re-sample next time delay
239:                 self._sampled = True
240:                 self._current_delay = self._delayer()
241: 
242:             # If our total time since last sample has surpassed our sampling timestep,
243:             # then we reset our timer and sampled flag
244:             if self._time_since_last_sample >= self._sampling_timestep:
245:                 if not self._sampled:
246:                     # If we still haven't sampled yet, sample immediately and warn user that sampling rate is too low
247:                     print(
248:                         f"Warning: sampling rate for observable {self.name} is either too low or delay is too high. "
249:                         f"Please adjust one (or both)"
250:                     )
251:                     # Get newest raw value, corrupt it, filter it, and set it as our current observed value
252:                     obs = np.array(self._filter(self._corrupter(self._sensor(obs_cache))))
253:                     self._current_observed_value = obs[0] if len(obs.shape) == 1 and obs.shape[0] == 1 else obs
254:                     # Update cache entry as well
255:                     obs_cache[self.name] = np.array(self._current_observed_value)
256:                     # Re-sample next time delay
257:                     self._current_delay = self._delayer()
258:                 self._time_since_last_sample %= self._sampling_timestep
259:                 self._sampled = False
260: 
261:     def reset(self):
262:         """
263:         Resets this observable's internal values (but does not reset its sensor, corrupter, delayer, or filter)
264:         """
265:         self._time_since_last_sample = 0.0
266:         self._current_delay = self._delayer()
267:         self._current_observed_value = 0 if self._is_number else np.zeros(self._data_shape)
268: 
269:     def is_enabled(self):
270:         """
271:         Determines whether observable is enabled or not. This observable is considered enabled if its values
272:         are being continually computed / updated during each update() call.
273: 
274:         Returns:
275:             bool: True if this observable is enabled
276:         """
277:         return self._enabled
278: 
279:     def is_active(self):
280:         """
281:         Determines whether observable is active or not. This observable is considered active if its current observation
282:         value is being returned in self.obs.
283: 
284:         Returns:
285:             bool: True if this observable is active
```

## bindings: d_alignment_pilot/external/robosuite-51cc01785bab80ffeed20da15e67d7dd4140e76a/robosuite/utils/binding_utils.py

```text
1148:         self._render_context_offscreen = render_context
1149: 
1150:     def get_state(self):
1151:         """Return MjSimState instance for current state."""
1152:         return MjSimState(
1153:             time=self.data.time,
1154:             qpos=np.copy(self.data.qpos),
1155:             qvel=np.copy(self.data.qvel),
1156:         )
1157: 
1158:     def set_state(self, value):
1159:         """
1160:         Set internal state from MjSimState instance. Should
1161:         call @forward afterwards to synchronize derived quantities.
1162:         """
1163:         self.data.time = value.time
1164:         self.data.qpos[:] = np.copy(value.qpos)
1165:         self.data.qvel[:] = np.copy(value.qvel)
1166: 
1167:     def set_state_from_flattened(self, value):
1168:         """
1169:         Set internal mujoco state using flat mjstate array. Should
1170:         call @forward afterwards to synchronize derived quantities.
1171: 
1172:         See https://github.com/openai/mujoco-py/blob/4830435a169c1f3e3b5f9b58a7c3d9c39bdf4acb/mujoco_py/mjsimstate.pyx#L54
1173:         """
1174:         state = MjSimState.from_flattened(value, self)
1175: 
1176:         # do this instead of @set_state to avoid extra copy of qpos and qvel
1177:         self.data.time = state.time
1178:         self.data.qpos[:] = state.qpos
1179:         self.data.qvel[:] = state.qvel
1180: 
1181:     def free(self):
1182:         # clean up here to prevent memory leaks
1183:         del self._render_context_offscreen
1184:         del self.data
1185:         del self.model
```

## robot_sensors: d_alignment_pilot/external/robosuite-51cc01785bab80ffeed20da15e67d7dd4140e76a/robosuite/robots/robot.py

```text
401:         """
402: 
403:         # eef features
404:         @sensor(modality=modality)
405:         def eef_pos(obs_cache):
406:             return np.array(self.sim.data.site_xpos[self.eef_site_id[arm]])
407: 
408:         @sensor(modality=modality)
409:         def eef_quat(obs_cache):
410:             """
411:             Args:
412:                 obs_cache (dict): A dictionary containing cached observations.
413: 
414:             Returns:
415:                 numpy.ndarray: The quaternion representing the orientation of the end effector *body*
416:                 in the mujoco world coordinate frame.
417: 
418:             Note:
419:                 In robosuite<=1.5, eef_quat has been queried from the body instead
420:                 of the site and has thus been inconsistent with the eef_pos, which queries from the site.
421: 
422:                 This inconsistency has been raised in issue https://github.com/ARISE-Initiative/robosuite/issues/298.
423: 
424:                 Datasets collected with robosuite<=1.4 have use the eef_quat queried from the body, so we keep this key.
425:                 New datasets should ideally use the logic in eef_quat_site.
426: 
427:                 In a later robosuite release, we will directly update eef_quat to query
428:                 the orientation from the site.
429:             """
430:             return T.convert_quat(self.sim.data.get_body_xquat(self.robot_model.eef_name[arm]), to="xyzw")
431: 
432:         @sensor(modality=modality)
433:         def eef_quat_site(obs_cache):
434:             """
435:             Args:
436:                 obs_cache (dict): A dictionary containing cached observations.
437: 
438:             Returns:
439:                 numpy.ndarray: The quaternion representing the orientation of the end effector *site*
440:                 in the mujoco world coordinate frame.
441: 
442:             Note:
443:                 In robosuite<=1.5, eef_quat_site has been queried from the body instead
444:                 of the site and has thus been inconsistent with the eef_pos, which queries from the site.
445: 
446:                 This inconsistency has been raised in issue https://github.com/ARISE-Initiative/robosuite/issues/298
447: 
448:                 Datasets collected with robosuite<=1.4 have use the eef_quat queried from the body, so we keep this key.
449:                 New datasets should ideally use the logic in eef_quat_site.
450: 
451:                 In a later robosuite release, we will directly update eef_quat to query
452:                 the orientation from the site, and then remove this eef_quat_site key.
453:             """
454:             return T.mat2quat(self.sim.data.site_xmat[self.eef_site_id[arm]].reshape((3, 3)))
455: 
456:         # only consider prefix if there is more than one arm
457:         pf = f"{arm}_" if len(self.arms) > 1 else ""
458: 
459:         sensors = [eef_pos, eef_quat, eef_quat_site]
460:         names = [f"{pf}eef_pos", f"{pf}eef_quat", f"{pf}eef_quat_site"]
461: 
462:         # add in gripper sensors if this robot has a gripper
463:         if self.has_gripper[arm]:
464: 
465:             @sensor(modality=modality)
466:             def gripper_qpos(obs_cache):
467:                 return np.array([self.sim.data.qpos[x] for x in self._ref_gripper_joint_pos_indexes[arm]])
468: 
```
