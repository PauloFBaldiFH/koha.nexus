"""Pinned bundled translations, with explicit legacy-image capabilities."""
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent

def catalog(recipe=5):
    data=json.loads((BASE/'languages.json').read_text())
    return [dict(row,index=i if recipe>=5 else row['legacy_index']) for i,row in enumerate(data['languages'])
            if recipe>=5 or row['legacy_index'] is not None]

def normalize(value, recipe=5):
    if not isinstance(value,str):return ''
    value=value.replace('_','-').lower()
    aliases={'pt':'pt-br','por':'pt-br','eng':'en','spa':'es','fra':'fr','fre':'fr','deu':'de','ger':'de','jp':'ja','sr':'sr-cyr'}
    value=aliases.get(value,value)
    return next((row['code'] for row in catalog(recipe) if row['code'].lower()==value),'')

def account_code(value, recipe=5):
    code=normalize(value,recipe)
    if recipe>=5:return code
    return {'pt-BR':'pt_BR','en':'en','es':'es'}.get(code,'')

def suggest(panel_language, recipe=5):
    return normalize(panel_language,recipe) or 'en'

def configuration(compose,recipe=5):
    env=compose['services']['ui'].get('environment',{})
    rows=catalog(recipe)
    active=[r['code'] for r in rows if str(env.get('DSPACE_LANGUAGES_'+str(r['index'])+'_ACTIVE','true')).lower()=='true']
    return dict(available=[dict(code=r['code'],label=r['label']) for r in rows],active=active,
                fallback=env.get('DSPACE_FALLBACKLANGUAGE','en'),
                accounts=[r['code'] for r in rows if account_code(r['code'],recipe)])

def edit(compose,request,recipe=5):
    check_default_mapping(compose,recipe)
    rows=catalog(recipe);allowed={r['code'] for r in rows}
    fallback=normalize(request.get('fallback'),recipe)
    selected=request.get('active')
    if not fallback or not isinstance(selected,list) or not selected or any(not isinstance(c,str) or c not in allowed for c in selected) or len(set(selected))!=len(selected) or fallback not in selected:
        raise ValueError('Choose available languages and keep the fallback language active.')
    env=compose['services']['ui'].setdefault('environment',{})
    env['DSPACE_FALLBACKLANGUAGE']=fallback
    for row in rows:env['DSPACE_LANGUAGES_'+str(row['index'])+'_ACTIVE']=str(row['code'] in selected).lower()
    return configuration(compose,recipe)

def check_default_mapping(compose,recipe):
    env=compose['services']['ui'].get('environment',{})
    path=env.get('DSPACE_APP_CONFIG_PATH','')
    if path and (recipe<5 or path!='/app/config/nexus-languages.json'):
        raise ValueError('The interface uses a custom configuration file. Review its language mapping before applying this change.')
    if any(k.startswith('DSPACE_LANGUAGES_') and k.endswith(('_CODE','_LABEL')) for k in env):
        raise ValueError('Custom language codes or labels were preserved. Review their mapping before applying this change.')

def migrate_environment(compose,old_recipe):
    check_default_mapping(compose,old_recipe)
    previous=configuration(compose,old_recipe)
    return edit(compose,{'active':previous['active'],'fallback':previous['fallback']},5)
