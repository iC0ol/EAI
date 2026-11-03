# CPU Pre-flight 与有限修复派发审查

**独立性说明**：以下在读取 `notes/01_Codex初始针对性审查.md` 之前形成；未运行代码/GL/模型。

## 结论

**APPROVE `CPU_PRE_FLIGHT_AND_REPAIR_ONLY`**，但仅限真实 CPU 导入链与已证实工程修复；**不是 GPU、Stage1 或 Stage2 放行**。最终 GPU 代码/协议仍须两审准确 SHA。

## 具体意见

1. **真实预检方向正确**：同一解释器、cwd、真实入口加载器；检查 `experiment_lib/utils/eval/models/cam_embedding` 的实际 `__file__/spec/sys.modules` 身份，以及 `ROOT/DATA/atomic_json/utc` 语义。不得用 AST/mock 代替；R1 只修已知 `common` 冲突，R2 只修预检暴露的新错误，最多两轮，不另立阶段重置次数。

2. **预检覆盖空洞**：一个 GPU 预检不可能同时验证 `input` 的 `make_env/Dataset/Evaluator/embedder` 与 `model` 的 strict load；两者路径不同。建议明确：
   - GPU 预检只做**真实 input 初始化**（不 render、不 read、不 ACT）；
   - **model strict load 在 Stage1 model worker 的第一次 ACT 之前**完成并保存证据，失败即停；不额外增加 worker。
   若坚持两项都 GPU 预检，则 worker 上限需相应调整，不能仍称 5。  
   CPU 预检不得实例化 env/model；若 import 触发 CUDA/EGL，立即记录具体模块并停止，不把 CPU 通过当 GPU 通过。

3. **预算**：1800 总 GPU 分配秒；工程预检≤180、Stage1≤600、Stage2 用剩余，量级可成立但非时间保证。Stage2 另加 **≤80 render/160 readPixels**，必须与 Stage1 的 12/24 分开累计；总 render/read 为 92/184。GPU 预检不做额外 forward/render/step；若触发则计入既定计数，不能当免费 debug。5 worker（2 预检+input+model+closed loop）与上述“GPU 预检只做 input init、strict load 在 S1”自洽。

4. **Stage2 旧断言**：必须取消旧 `closed_loop` 的两道硬门——新健康 RGB 强制等于未验证健康的旧 `manifest['clean_RGB']`，以及新预测强制等于旧 0/32 动作；保留 `restore_root` 的 XML/state/RNG 哈希和状态精确恢复。该修改只移除失效工程对照，不改变模型、执行动作、成功/reach/grasp 指标；旧图像/动作差异应记录为解释性证据。

5. **Stage2 解释**：8 root×2 相机不是 16 独立任务；Stage1 数值阳性不等于任务阳性，Stage2 过门也不等于 F 有效。Stage2 的最终筛选阈值/相机-视角解释须在 S2 执行前冻结，不得事后挑 root/相机或追加 seed；Stage3 只交方案，不执行。

**批准边界**：只批准真实 CPU 导入预检、最多 R1/R2 修复及其证据；GPU/Stage1/Stage2 仍按阶段门另行派发，不能写成自动放行。
