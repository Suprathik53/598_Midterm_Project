# Findings (measured data)

Input: `results\core-12297017`. 72 successful runs; 0 failed/invalid runs. Values are medians; ranges show trial minima and maxima.

## N=512

- P=1: Jacobi 0.250299 s [0.249795, 0.250691]; CG 0.0426081 s [0.0423501, 0.0427573]; Jacobi/CG = 5.87; iterations 500 vs 40.
- P=2: Jacobi 0.136418 s [0.136074, 0.140242]; CG 0.0224498 s [0.0223709, 0.0237151]; Jacobi/CG = 6.08; iterations 500 vs 40.
- P=4: Jacobi 0.0773729 s [0.0767918, 0.0773827]; CG 0.0144767 s [0.0142117, 0.0147858]; Jacobi/CG = 5.34; iterations 500 vs 40.
- P=8: Jacobi 0.0455508 s [0.0449925, 0.0537398]; CG 0.00974216 s [0.00963301, 0.00991714]; Jacobi/CG = 4.68; iterations 500 vs 40.
- P=16: Jacobi 0.0309752 s [0.0306213, 0.0310778]; CG 0.00636902 s [0.00635401, 0.00669816]; Jacobi/CG = 4.86; iterations 500 vs 40.
- P=32: Jacobi 0.0232995 s [0.0229933, 0.0235237]; CG 0.00449835 s [0.00449178, 0.00450628]; Jacobi/CG = 5.18; iterations 500 vs 40.

## N=1024

- P=1: Jacobi 0.998823 s [0.996057, 1.00142]; CG 0.111298 s [0.11052, 0.111879]; Jacobi/CG = 8.97; iterations 450 vs 24.
- P=2: Jacobi 0.495091 s [0.492211, 0.516418]; CG 0.0665354 s [0.0664424, 0.0668358]; Jacobi/CG = 7.44; iterations 450 vs 24.
- P=4: Jacobi 0.246924 s [0.243381, 0.300741]; CG 0.0309138 s [0.0307245, 0.0309285]; Jacobi/CG = 7.99; iterations 450 vs 24.
- P=8: Jacobi 0.132967 s [0.132913, 0.136134]; CG 0.0190227 s [0.0185352, 0.019086]; Jacobi/CG = 6.99; iterations 450 vs 24.
- P=16: Jacobi 0.0819914 s [0.0810143, 0.0824363]; CG 0.013028 s [0.0128581, 0.0130781]; Jacobi/CG = 6.29; iterations 450 vs 24.
- P=32: Jacobi 0.0591518 s [0.0589415, 0.0605502]; CG 0.0107543 s [0.0105504, 0.0107614]; Jacobi/CG = 5.5; iterations 450 vs 24.

## Communication crossover

- cg, N=512: between P=16 and P=32; uncertainty flag (trial range crosses 0.5): False; P: median fraction [min,max] = 1:0.0003 [0.0003,0.0003]; 2:0.0455 [0.0445,0.1032]; 4:0.1434 [0.1374,0.1564]; 8:0.2239 [0.2230,0.2325]; 16:0.3874 [0.3829,0.4215]; 32:0.6928 [0.6882,0.6944].
- cg, N=1024: not observed; uncertainty flag (trial range crosses 0.5): False; P: median fraction [min,max] = 1:0.0002 [0.0002,0.0003]; 2:0.1812 [0.1810,0.1866]; 4:0.0606 [0.0580,0.0673]; 8:0.0999 [0.0996,0.1322]; 16:0.1642 [0.1636,0.1799]; 32:0.2884 [0.2819,0.2961].
- jacobi, N=512: between P=16 and P=32; uncertainty flag (trial range crosses 0.5): False; P: median fraction [min,max] = 1:0.0003 [0.0002,0.0003]; 2:0.0854 [0.0755,0.0975]; 4:0.1611 [0.1467,0.1624]; 8:0.2573 [0.2438,0.3639]; 16:0.3852 [0.3849,0.3926]; 32:0.6457 [0.6447,0.6505].
- jacobi, N=1024: not observed; uncertainty flag (trial range crosses 0.5): False; P: median fraction [min,max] = 1:0.0002 [0.0001,0.0002]; 2:0.0797 [0.0597,0.1102]; 4:0.0551 [0.0482,0.2259]; 8:0.1251 [0.0974,0.1282]; 16:0.2064 [0.2060,0.2071]; 32:0.3429 [0.3361,0.3563].

Fractions are MPI call time divided by local compute plus MPI time; MPI includes waiting and imbalance, not just network transfers. The bracket is between sampled process counts, not a measured exact threshold. P=1 is on one node; P≥2 is distributed across two, so a bracket involving P=1 also changes topology. Three trials provide limited uncertainty information. See `../figures/communication_fraction.png` and `../figures/strong_scaling_runtime.png`.

Groups with time CV above 10%: jacobi N=512 P=8 (10.2%), jacobi N=1024 P=4 (12.2%). Same-P one-node vs two-node data were not collected, so an inter-node penalty cannot be isolated.
