"""Pure presentation planning. Validate the complete trace before calling this.

Source mathematics is immutable. Every source event occurs once in the plan's
coverage map, including events condensed into an explicitly labelled summary.
This policy is specific to the supported orthogonal_dyadic trace profile.
"""
from collections import Counter
from copy import deepcopy
import math

from dyadic_viz.storyboard import build_storyboard


def validate_recipe(recipe, trace):
    allowed = {'version', 'examples_per_case', 'retain_events', 'case_tags', 'formulas'}
    if not isinstance(recipe, dict) or set(recipe) - allowed:
        raise ValueError('Presentation must be an object with documented fields only')
    if recipe.get('version', 1) != 1:
        raise ValueError('Unsupported presentation version')
    count = recipe.get('examples_per_case', 1)
    if type(count) is not int or not 1 <= count <= 3:
        raise ValueError('examples_per_case must be an integer from 1 to 3')
    ids = {e['id'] for e in trace['events']}
    retain = recipe.get('retain_events', [])
    if not isinstance(retain, list) or any(not isinstance(i, str) or i not in ids for i in retain):
        raise ValueError('retain_events must reference existing source event IDs')
    tags = recipe.get('case_tags', {})
    if not isinstance(tags, dict) or any(k not in ids or not isinstance(v, str) or not v.strip() for k,v in tags.items()):
        raise ValueError('case_tags must map existing event IDs to nonempty case names')
    formulas = recipe.get('formulas', [])
    if not isinstance(formulas, list):
        raise ValueError('formulas must be a list')
    for f in formulas:
        if not isinstance(f, dict) or set(f) - {'after_event','expression','hold_seconds','narration'}:
            raise ValueError('Unknown formula fields')
        if f.get('after_event') not in ids or not isinstance(f.get('expression'), str) or not f['expression'].strip():
            raise ValueError('Formula needs an existing after_event and a nonempty expression')
        hold = f.get('hold_seconds', 2)
        if type(hold) not in (int,float) or not math.isfinite(hold) or not 0 < hold <= 30:
            raise ValueError('Formula hold_seconds must be finite and in (0,30]')
        if not isinstance(f.get('narration',''), str):
            raise ValueError('Formula narration must be text')


def _units(events):
    """One group/matrix action per unit, even inside very long LDE sweeps."""
    pending = []
    for event in events:
        kind = event['type']
        if kind in {'input','verification','recovery','complete','column_start'} and pending:
            yield pending
            pending = []
        pending.append(event)
        if kind in {'input','verification','recovery','complete','generator_applied',
                    'lde_reduced','column_integral','column_complete'}:
            yield pending
            pending = []
    if pending:
        yield pending


def _cases(unit, trace, operations, tags):
    cases = set()
    applying = [operations[e['payload']['operation_id']] for e in unit
                if e['type'] in {'generator_applied','sign_correction'}]
    if any(o['role']=='mixing' for o in applying):
        corrected = any(o['role']=='sign_correction' for o in applying)
        cases.add('mix:sign-correction' if corrected else 'mix:already-normalized')
        for op in applying:
            if op['role']=='mixing':
                before = trace['states'][op['before_state_id']]['focus']['lde']
                after = trace['states'][op['after_state_id']]['focus']['lde']
                cases.add('mix:lde-unchanged' if before==after else 'mix:lde-decreases')
    else:
        cases.update('operation:'+o['role'] for o in applying)
    for e in unit:
        if e['id'] in tags:
            cases.add('declared:'+tags[e['id']])
        if e['explanation']['rule_id']:
            cases.add('rule:'+e['explanation']['rule_id'])
        if e['type']=='lde_reduced':
            p=e['payload']
            delta=(trace['states'][p['before_state_id']]['focus']['lde']
                   -trace['states'][p['after_state_id']]['focus']['lde'])
            cases.add('lde:drop-one' if delta==1 else 'lde:drop-multiple')
    if not applying and not any(e['type']=='lde_reduced' for e in unit):
        cases.add('state:'+unit[-1]['type'])
    return sorted(cases)


def build_presentation(trace, *, mode='compact', recipe=None):
    if mode not in {'compact','full'}:
        raise ValueError('Presentation mode must be compact or full')
    recipe = deepcopy({} if recipe is None else recipe)
    validate_recipe(recipe, trace)
    board = build_storyboard(trace)
    source = board['events']
    operations = {o['id']:o for o in trace['operations']}
    retain = set(recipe.get('retain_events', []))
    formulas = recipe.get('formulas', [])
    retain.update(f['after_event'] for f in formulas)
    counts = Counter()
    rendered = []
    pending = []
    decisions = []
    used_ids = {e['id'] for e in source}

    def new_id(prefix):
        i=0
        while f'{prefix}_{i}' in used_ids:
            i+=1
        result=f'{prefix}_{i}'
        used_ids.add(result)
        return result

    def flush():
        if not pending:
            return
        first,last=pending[0],pending[-1]
        covered=[e['id'] for e in pending]
        op_ids=[e['payload']['operation_id'] for e in pending
                if e['type'] in {'generator_applied','sign_correction'}]
        text=(f'The intervening {len(op_ids)} recorded operations repeat cases already shown. '
              'Here are the exact states before and after these operations.' if op_ids else
              'The intervening column checks repeat cases already shown; no matrix operation is omitted here.')
        event=deepcopy(last)
        event.update(id=new_id('presentation_summary'),type='presentation_summary',
                     before_state_id=first['before_state_id'], source_event_ids=covered,
                     payload={'before_state_id':first['before_state_id'],'after_state_id':last['after_state_id'],
                              'operation_ids':op_ids},
                     narration={'text':text,'hold_seconds':1.2},
                     explanation={'rule_id':None,'summary':'Condensed recorded steps; no new proof claim.',
                                  'facts':[{'label':'Source events','text':', '.join(covered)}]})
        rendered.append(event)
        pending.clear()

    for unit in _units(source):
        cases=_cases(unit,trace,operations,recipe.get('case_tags',{}))
        novel=[c for c in cases if counts[c]<recipe.get('examples_per_case',1)]
        pinned=any(e['id'] in retain for e in unit)
        essential=any(e['type'] in {'input','verification','recovery','complete'} for e in unit)
        detailed=mode=='full' or bool(novel) or pinned or essential
        decisions.append({'source_event_ids':[e['id'] for e in unit], 'cases':cases,
                          'detail':detailed,'new_cases':novel,'pinned':pinned})
        if detailed:
            flush()
            for e in unit:
                item=deepcopy(e)
                item['source_event_ids']=[e['id']]
                if mode=='compact':
                    item['narration']['hold_seconds']=min(item['narration']['hold_seconds'],.65)
                rendered.append(item)
                for f in formulas:
                    if f['after_event']==e['id']:
                        annotation=deepcopy(item)
                        annotation.update(id=new_id('presentation_formula'),type='presentation_formula',
                            source_event_ids=[],before_state_id=item['after_state_id'],
                            payload={'expression':f['expression'],'anchor_event_id':e['id']},
                            narration={'text':f.get('narration',''),'hold_seconds':f.get('hold_seconds',2)},
                            explanation={'rule_id':None,'summary':'Author-supplied formula; review its mathematical meaning.', 'facts':[]})
                        rendered.append(annotation)
            counts.update(cases)
        else:
            pending.extend(unit)
    flush()
    coverage=[i for e in rendered for i in e['source_event_ids']]
    if coverage != [e['id'] for e in source]:
        raise ValueError('Presentation coverage must preserve every source event once, in order')
    board['events']=rendered
    board['presentation']={'version':1,'mode':mode,'recipe':recipe,'decisions':decisions,
        'source_event_count':len(source),'rendered_event_count':len(rendered),
        'condensed_source_events':sum(len(e['source_event_ids']) for e in rendered if e['type']=='presentation_summary')}
    return board
