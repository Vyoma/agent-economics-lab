==================================================================
  SENSITIVITY SWEEP  decision robustness analysis
==================================================================
  98 scenarios x 48-cell economic grid (8 incident x 6 remediation)
  incident_loss $0 to $50, remediation $0 to $5

  DECISION ROBUSTNESS across the economic assumption grid
  ----------------------------------------------------------
  ROBUST  (0 flips)        43/98  ###########.............  43.9%
  FRAGILE (1-2 flips)       0/98  ........................  0.0%
  BRITTLE (3+ flips)       55/98  #############...........  56.1%

  Max flips for a single scenario: 42/48
  55 scenarios produce a verdict that is an economic assumption
  artifact rather than a stable result. Do not publish a SCALE
  verdict from a scenario with 3+ flips without this report beside it.

  BASELINE FRAGILITY INDEX  (perturb baseline acceptable rate)
  ----------------------------------------------------------
   -50% baseline error   25/98 counterfactual flips  #####.............  25.5%  <- critical
   -25% baseline error    9/98 counterfactual flips  ##................  9.2%
   -10% baseline error    1/98 counterfactual flips  ..................  1.0%
   +10% baseline error    4/98 counterfactual flips  #.................  4.1%
   +25% baseline error    9/98 counterfactual flips  ##................  9.2%
   +50% baseline error   12/98 counterfactual flips  ##................  12.2%

  A baseline is always an estimate. These are its error bars.
  Report the fragility index alongside every SCALE verdict.
==================================================================
