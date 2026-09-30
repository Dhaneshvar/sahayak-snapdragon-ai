# Benchmarks

All numbers below are measured with `python benchmarks/benchmark.py --runs 5`
on the device listed. Nothing here is estimated.

## Device

| Item | Value |
|---|---|
| Laptop | _fill in, e.g. HP OmniBook X_ |
| Processor | _fill in, e.g. Snapdragon X Plus X1P-42-100_ |
| RAM | _fill in_ |
| Windows build | _fill in_ |
| Foundry Local version | _`foundry --version`_ |

## Results

| Stage | Model / engine | Runs on | Median (s) | Min (s) | Max (s) |
|---|---|---|---|---|---|
| OCR (sample form) | RapidOCR | CPU | | | |
| Explain (English) | _model id_ | NPU | | | |
| Explain (English) | _CPU variant id_ | CPU | | | |
| Ask (English) | _model id_ | NPU | | | |
| Explain (Hindi) | _model id_ | NPU | | | |

## Offline check

- [ ] Wi-Fi turned off, app restarted, full flow works (open → explain → ask → checklist)

## Notes

_Observations, e.g. NPU utilisation seen in Task Manager, Hindi quality, battery impact._
