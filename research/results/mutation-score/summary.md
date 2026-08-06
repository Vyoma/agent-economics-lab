==================================================================
  MUTATION SCORE  agent-economics-lab decision harness
==================================================================
  1176 mutants injected across 98 scenarios, 6 gates, 2 operators
  156 equivalent mutants excluded (unmutated verdict was already SCALE)

  REMOVAL  (510 scored mutants)
    fixed-contract engine    510/510 killed  (100.0%)
    dynamic-coverage engine  487/510 killed  (95.5%)
    note: the fixed-contract result here is forced. Required coverage loses a
          sole provider, so INCOMPLETE is the only reachable answer. Not evidence.

  SUBSTITUTION  (510 scored mutants)
    fixed-contract engine    487/510 not SCALE  (95.5%)
    dynamic-coverage engine  487/510 not SCALE  (95.5%)
    contract digest changed  588/588 mutants (implementation fingerprint)
    note: coverage still looks satisfied, so neither engine's routing DETECTS this.
          A non-SCALE result here means other gates were also failing and masked
          the substitution. It is not detection. Only the changed digest surfaces it,
          and only when the check body itself was substituted.

  Surviving mutants by dimension (fixed contract)
  dimension             removal   substitution
  ----------------------------------------------
  outcome_quality             0              2  ####..............
  unit_economics              0              1  ##................
  tail_risk                   0              8  ##################
  business_value              0              1  ##................
  counterfactual              0              3  #######...........
  runtime_caps                0              8  ##################

  HARNESS MUTATION SCORE (substitution): 95.5%

  Read it this way. The coverage contract makes gate deletion
  undetectable-by-omission, which is a real property but a forced one.
  Against a gate that keeps its declared identity and stops enforcing,
  the fixed contract scores no better than the dynamic one. The
  implementation fingerprint in the decision-contract digest is the
  only thing that distinguishes them.

  'All enabled checks passed' is not 'all required checks passed'.
  'All required checks ran' is not 'all required checks enforced'.
==================================================================
