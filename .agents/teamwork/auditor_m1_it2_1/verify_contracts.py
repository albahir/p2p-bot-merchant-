import re

# 1. Verify task count
tasks_content = open(r'.specify/specs/023-ai-market-predictor/tasks.md', encoding='utf-8').read()
task_ids = re.findall(r'- \[(?: |x)\] (T23\.\d+):', tasks_content)
print(f'Total tasks found: {len(task_ids)}')
assert len(task_ids) == 26, f'Expected 26 tasks, got {len(task_ids)}'
assert task_ids[0] == 'T23.1'
assert task_ids[-1] == 'T23.26'
print('Task IDs match T23.1 to T23.26 continuously!')

# 2. Verify absence of legacy English enums
assert 'MarketDirection' not in tasks_content, 'MarketDirection still present in tasks.md'
assert 'TimeHorizon' not in tasks_content, 'TimeHorizon still present in tasks.md'
print('Legacy English enums absent from tasks.md!')

# 3. Verify activation floor in docs/macro_usdt_taxonomy.md and plan.md
tax_content = open(r'docs/macro_usdt_taxonomy.md', encoding='utf-8').read()
plan_content = open(r'.specify/specs/023-ai-market-predictor/plan.md', encoding='utf-8').read()
assert 'max(0.0' in tax_content or r'\max(0.0' in tax_content
assert 'calc_activation' in plan_content
print('Activation floor verified in taxonomy and plan!')

# 4. Verify pipe-delimited hashing standard
assert 'pipe-delimited' in plan_content.lower() or 'delimitada por tuber' in plan_content.lower()
assert '{prev_hash}|{timestamp_iso}|{direction}|{timeframe}|{confidence}|{model}|{justification}' in tasks_content
print('Pipe-delimited standard verified in plan and tasks!')

# 5. Check TaxonomyCategory and Prompt 7.1 consistency
prompt_categories = [
    'GASTO_PUBLICO_PATRIA',
    'INTERVENCION_CAMBIARIA_BCV',
    'POLITICA_MONETARIA_LIQUIDEZ',
    'CALENDARIO_FISCAL_SENIAT',
    'REGULACION_CAMBIARIA_BANCARIA',
    'OPERATIVA_MERCADO_P2P',
    'GEOPOLITICA_PETROLERA'
]

for cat in prompt_categories:
    assert f'{cat} = "{cat}"' in plan_content, f'Missing category enum {cat} in plan.md'
    assert cat in tax_content, f'Missing category {cat} in taxonomy.md'
print('All 7 canonical taxonomy categories verified in plan.md and taxonomy.md!')

# 6. Verify resumen_factico is ASCII (no accents in attribute name)
assert 'resumen_factico: str' in plan_content
assert 'resumen_fáctico' not in plan_content
print('resumen_factico is ASCII and without accent!')

# 7. Check code field in MacroEventItem
assert 'code: str' in plan_content
print('code field in MacroEventItem verified!')

print('ALL 7 REMEDIATION VERIFICATION CHECKS PASSED SUCCESSFULLY!')
