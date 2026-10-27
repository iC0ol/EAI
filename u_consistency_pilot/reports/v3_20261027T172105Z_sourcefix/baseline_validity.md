# 初始 G 基线有效性

PASS。固定训练 seed 270727；flow/MLP 与历史匹配的加强 G 预训练均实际执行。

```json
{
  "status": "PASS",
  "check_scope": "finite optimization, held-out fitting relative to constant/history controls; thresholds catch grossly broken fitting, never require an almost unique inverse map",
  "gross_failure_rule_frozen_before_training": "MLP val MSE >1.5*constant or flow K4-mean MSE >2*constant, or nonfinite; interpret flow stochastic K1 separately",
  "models": [
    {
      "name": "flow",
      "kind": "flow",
      "phase": "idm",
      "actual_updates": 6500,
      "best_val_mse": 0.19693363800048827,
      "elapsed_seconds": 224.1722682439722,
      "seed": 270727,
      "checkpoint": ".work/20261027T172105Z_sourcefix/flow_best.pt"
    },
    {
      "name": "mlp",
      "kind": "mlp",
      "phase": "idm",
      "actual_updates": 4750,
      "best_val_mse": 0.24010867919921874,
      "elapsed_seconds": 28.356181162409484,
      "seed": 270727,
      "checkpoint": ".work/20261027T172105Z_sourcefix/mlp_best.pt"
    },
    {
      "name": "history",
      "kind": "history",
      "phase": "idm",
      "actual_updates": 3500,
      "best_val_mse": 0.487213037109375,
      "elapsed_seconds": 20.23230362869799,
      "seed": 270727,
      "checkpoint": ".work/20261027T172105Z_sourcefix/history_best.pt"
    },
    {
      "name": "strong_base",
      "kind": "strong",
      "phase": "idm",
      "actual_updates": 4250,
      "best_val_mse": 0.2397670623779297,
      "elapsed_seconds": 24.512779276818037,
      "seed": 270727,
      "checkpoint": ".work/20261027T172105Z_sourcefix/strong_base_best.pt"
    }
  ],
  "evaluations": {
    "flow": {
      "val": {
        "mse": 0.19609585264700435,
        "constant_mse": 0.9031224747155695,
        "n_blocks": 2000,
        "mse_K1": 0.20314633816385805,
        "mean_sampling_variance_per_coordinate": 0.010123166255652905,
        "K4_mean_sampling_variance_estimate": 0.002530791563913226
      },
      "audit": {
        "mse": 0.21948984380674955,
        "constant_mse": 0.9868372073915482,
        "n_blocks": 6000,
        "mse_K1": 0.228298411095747,
        "mean_sampling_variance_per_coordinate": 0.011382203549146652,
        "K4_mean_sampling_variance_estimate": 0.002845550887286663
      }
    },
    "mlp": {
      "val": {
        "mse": 0.24010867516152512,
        "constant_mse": 0.9031224747155695,
        "n_blocks": 2000
      },
      "audit": {
        "mse": 0.27196290451624655,
        "constant_mse": 0.9868372073915482,
        "n_blocks": 6000
      }
    },
    "history": {
      "val": {
        "mse": 0.48721304031666024,
        "constant_mse": 0.9031224747155695,
        "n_blocks": 2000
      },
      "audit": {
        "mse": 0.5671049946614203,
        "constant_mse": 0.9868372073915482,
        "n_blocks": 6000
      }
    },
    "strong": {
      "val": {
        "mse": 0.23976706186882998,
        "constant_mse": 0.9031224747155695,
        "n_blocks": 2000
      },
      "audit": {
        "mse": 0.2664881955162546,
        "constant_mse": 0.9868372073915482,
        "n_blocks": 6000
      }
    }
  },
  "successor_information_gain_matched_history": 0.24744597844783026,
  "successor_information_gain_mlp_vs_history_unmatched_inputs": 0.24710436515513512,
  "successor_information_gain_flow_vs_history_unmatched_inputs": 0.2911171876696559,
  "initial_G_frozen": true,
  "flow_reference": "4 TransformerEncoder layers, width192, 3 heads; two latent prefix tokens and one noisy-action suffix; prefix cannot attend suffix; beta(1.5,1), one Euler step",
  "ACID_difference": "No official weights; trained <=20k versus paper 200k;10D five-control-step chunks; whole-source split; microbatch64 accumulated to256; single training seed; flow K4 mean added as diagnostic",
  "checkpoints": {
    "flow": "11642e9b49c8028c7d7cf569fe062ca6c8fb81975055fb2ac49159362b419315",
    "mlp": "a887213502371b04a346952a404d253d5d9433ff76987c7f3430fd1e273bed82",
    "history": "c8fd5bb36945d703949a918a3ccf0f80c9f20e00554fa0da737730aa10e757e6",
    "strong_base": "944d624a6b957ade5e98971d270a2df97f4e3746bbd77bccd2c27d1adf788d76"
  },
  "constant_action": [
    -0.01910930079182883,
    -0.006902965418214389,
    -0.02039921708073803,
    -0.016840151599384505,
    -0.017871160557204776,
    -0.007219957119388238,
    -0.02147975022783901,
    -0.004674589450273946,
    -0.023572713080427132,
    -0.0044996290003873245
  ],
  "MSE_units": "standardized training actions; inference G is de-normalized and residual scores use original environment control units"
}
```

MSE 是拟合/信息诊断，未要求端点到动作唯一；与 ACID 的结构/更新预算差异已披露。离线 6000 块只用于误差和动作支持，不用于 b 拟合。加强 G 在后续 cal-fit 标签阶段继续训练，总更新不超过 20000。


<!-- V3_MATCHED_G_FINAL -->
匹配历史/额外标签加强 G 的实际结果（cal-val 只验证；192 个独特 cal-fit 标签的重复加权不计作新样本）：

```json
{
  "status": "PASS",
  "model": {
    "name": "strong",
    "kind": "strong",
    "phase": "matched_cal_fit",
    "actual_updates": 3500,
    "best_val_mse": 0.6874459266662598,
    "elapsed_seconds": 20.266616156790406,
    "seed": 270727,
    "checkpoint": ".work/20261027T172105Z_sourcefix/strong_best.pt"
  },
  "pretrained_model": "strong_base_best.pt",
  "original_unique_train_blocks": 10000,
  "extra_unique_cal_fit_labels": 192,
  "cal_val_labels_validation_only": 64,
  "cal_fit_oversampling_copies": 52,
  "approximate_fit_sampling_weights": [
    0.5,
    0.5
  ],
  "input": "same 3 historical latents and 2 previous action blocks as b; plus real/predicted successor latent, no candidate A",
  "initial_pretrain_update_cap": 12000,
  "additional_update_cap": 8000,
  "combined_update_cap": 20000,
  "checkpoint_sha256": "b50f81b426ce67e939f5b6b1940226ab574531f01317e8d6d18cb221736f0e68",
  "cal_val_constant_MSE": 0.9657938349852498,
  "gross_fitting_guard": "best cal-val MSE <=1.5*same-label constant prediction MSE; does not require a unique inverse map"
}
```


<!-- V3_SOURCE_ANCESTRY_FINAL -->
来源隔离使用保守的精确初始状态家族，各家族101条metadata轨迹整体随组；未宣称掌握原始采集者全部谱系。实际独立分组数：{"train": 148, "val": 18, "audit": 19}；metadata episode数：{"train": 7123, "val": 1212, "audit": 1764}。18000个逆转移按原始current/successor/action精确去重，源分组交集为空。详见source_isolation_validation.json；前序缓存在G训练前已作废，F预训练见过全部公开分布。
