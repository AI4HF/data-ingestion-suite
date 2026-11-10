# ulslo-deploy person-sliced execution

`ulslo-deploy.json`'s eight `SqlSource` bindings all read a whole table
(`tableName`). toFHIR accumulates the whole mapped result set in memory
before writing (no streaming/`foreachBatch` path), so five of the eight
mappings (`condition-mapping`, `encounter-mapping`, `medication-mapping`,
`measurement-mapping`, `observation-mapping`, `procedure-mapping` — six,
see `slice-plan.json`) must be executed as a sequence of `person_id`-ordinal
SLICES instead of one whole-table pass, or they exhaust the JVM heap
(exit 52).

- `slice-plan.json` — the sizing plan: bucket width (persons) and slice
  count per mapping, derived from a measured row-count distribution
  (`uls-lisboa-ocidental/teras-cluster-uls-lisboa-ocidental` run
  `34442391625`), fitted against the two established RSS/rowcount points.
- `render_sliced_job.py` — given a mapping name and a 0-based slice index,
  rewrites that mapping's `tableName` bindings into `query` bindings bounded
  to that slice's ordinal range and emits a complete, independently
  deployable toFHIR job JSON (`<id>-<mapping>-slice-<NNN>`).
- Orchestration (resumable sequential execution, progress tracked so a
  failed pass never restarts the whole table from zero) lives in
  `uls-lisboa-ocidental/teras-cluster-uls-lisboa-ocidental`,
  `.github/workflows/zta-ai4hf-dis-run-sliced.yml`.

Slice boundaries are expressed as `row_number()` ORDINALS over
`person_id` order, never as literal `person_id` values, so no rendered job
JSON, log, or report carries a patient-identifying key.

## Not yet done

- `slice-plan.json`'s per-mapping bucket widths are extrapolated linearly
  from a single 200-person-bucket measurement; only slice 0 of
  `procedure-mapping` (the tightest mapping) has been run live against the
  real engine at the time of this PR. The remaining slices, and the other
  five sliced mappings, should be run and their actual peak RSS compared to
  the estimate before this plan is trusted at full scale.
