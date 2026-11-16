"""The eight confirmed themes. Descriptions are not scores or classifiers."""
from .errors import AppError

VERSION = 'initial-v0.1'
OPTIONS = {
    'Q1': [('follows_plan','基本按照医嘱服药'),('occasional_delay','偶尔延迟但通常不忘记'),('unintentional_miss','有时因忘记而漏服'),('self_adjusted','有时因想法或顾虑主动推迟或停止')],
    'Q2': list(zip('forget irregular_routine busy outside complexity unclear_use stockout side_effects long_term_effects no_symptoms low_effect fatigue low_energy privacy access cost none other'.split(),
                  ['容易忘记','作息不规律','工作学习太忙','外出不方便','步骤复杂','不清楚用法','药品未补充','担心副作用','担心长期影响','无症状时觉得不必服','效果不明显','用药厌倦','压力或精力不足','不愿被发现','购药不便','经济负担','以上都没有','其他'])),
    'Q3': list(zip('follow_advice doubts consider_change has_changed'.split(), ['仍按医嘱坚持','知道需要但偶有疑问','有时觉得可以少服或不服','曾自行调整或中断'])),
    'Q4': list(zip('side_effects long_term_effects dependence efficacy disease_progression cost none'.split(), ['副作用','长期影响','依赖','药效','疾病进展','经济成本','没有上述担心'])),
    'Q5': list(zip('sleep_change meal_change shift travel social no_medicine none'.split(), ['起睡时间变化','三餐不固定','轮班或安排变化','差旅外出','会议课堂或社交','忘带药品','没有这些影响'])),
    'Q6': [(str(i+1), x) for i,x in enumerate(['完全没有把握','不太有把握','一般','比较有把握','非常有把握'])],
    'Q7': list(zip('necessity purpose dose_use meal_sleep missed_delayed followup none'.split(), ['长期服药必要性','药物作用','剂量和服法解释','时间与餐睡关系','漏服或延迟时如何咨询','复诊或咨询时机','目前基本清楚'])),
    'Q8': list(zip('timed_reminder habit_anchor context_reminder privacy_reminder plain_knowledge organize_plan emotional_support family_support none'.split(), ['时间提醒','习惯关联','忙碌外出时提醒','隐私提醒','易懂知识','整理药单','疲惫时支持','经同意的家庭帮助','暂不需要更多帮助']))
}
PROMPTS = ['最近一个月，你的实际用药情况更接近哪一种？','哪些事情最容易让你难以坚持用药？','身体好转或没有明显症状时，你怎样看待继续服药？','对于目前的用药，你最担心什么？','什么情况下，你容易错过原定时间？','忙碌、疲惫或日程变化时，你有多大把握按医嘱完成？','理解和执行用药安排时，你最需要弄清楚什么？','你最希望平台提供哪些帮助？']
INTERACTIONS = ['scenario','multi_rank','scenario','multi_concern','multi_frequency','confidence','multi_concern','multi_rank']


def definition():
    return {'questionnaire_id':'initial','version':VERSION,
            'purpose':'八个主题帮助整理自报情况和支持偏好，不等同原研究量表、CAS预测或客观服药验证。家人不了解时请选择不清楚。',
            'themes':[{'question_id':q,'prompt':PROMPTS[i],'interaction':INTERACTIONS[i],
                       'options':[{'code':c,'label':label} for c,label in OPTIONS[q]],
                       'allows_unknown':True,'allows_not_applicable':True} for i,q in enumerate(OPTIONS)]}


def validate_answers(answers):
    for q, answer in answers.items():
        if answer['state'] != 'answered':
            continue
        value = answer['value']
        fields = {'Q1':{'primary','additional'},'Q2':{'selected','top_ranked','other_text'},
                  'Q3':{'choice'},'Q4':{'selected','top_concerns','intensity'},
                  'Q5':{'selected','frequency'},'Q6':{'confidence_level'},'Q7':{'selected'},'Q8':{'selected','ranked'}}[q]
        allowed = {c for c,_ in OPTIONS[q]}
        valid = set(value) == fields
        if not valid:
            raise AppError(422,'INVALID_ANSWER','答案字段与当前题目不一致')
        if q == 'Q1':
            valid = value['primary'] in allowed and isinstance(value['additional'],list)
            if valid:
                valid = all(isinstance(x,str) and x in allowed and x != value['primary'] for x in value['additional']) and len(set(value['additional'])) == len(value['additional'])
        elif q == 'Q3':
            valid = isinstance(value['choice'],str) and value['choice'] in allowed
        elif q == 'Q6':
            level = value['confidence_level']
            valid = type(level) is int and 1 <= level <= 5
        else:
            selected = value['selected']
            valid = isinstance(selected,list) and bool(selected) and all(isinstance(x,str) and x in allowed for x in selected)
            if valid:
                valid = len(set(selected)) == len(selected) and ('none' not in selected or len(selected) == 1)
            rank_key = {'Q2':'top_ranked','Q4':'top_concerns','Q8':'ranked'}.get(q)
            if valid and rank_key:
                ranked = value[rank_key]
                valid = isinstance(ranked,list) and all(isinstance(x,str) and x in selected for x in ranked) and len(set(ranked)) == len(ranked) and len(ranked) <= (2 if q=='Q4' else 3)
            if valid and q=='Q2':
                text = value['other_text']
                valid = (isinstance(text,str) and 1 <= len(text.strip()) <= 200) if 'other' in selected else text is None
            if valid and q=='Q4':
                intensity = value['intensity']
                valid = intensity is None or (type(intensity) is int and 0<=intensity<=4)
            if valid and q=='Q5':
                valid = value['frequency'] in (None,'never','occasionally','often')
            # These arrays are sets; ranking arrays preserve user order.
            if valid:
                value['selected'] = sorted(selected)
        if not valid:
            raise AppError(422,'INVALID_ANSWER','请检查选项、互斥项、排序及程度范围')
    return answers


def unavailable_cas():
    return {'status':'unavailable','value':None,'reason':'CAS输入映射、模型与预处理尚未适配和验证；本页不生成预测',
            'model_version':None,'preprocessing_version':None}


def descriptive_profile(response):
    answers = response['answers']
    any_answer = any(a['state']=='answered' for a in answers.values())
    factors = []
    for q in ('Q2','Q4','Q5'):
        a = answers[q]
        if a['state'] == 'answered':
            value = a['value']; labels = dict(OPTIONS[q])
            ordering = value.get('top_ranked') or value.get('top_concerns') or value['selected']
            factors.append({'label':{'Q2':'你选择的困难','Q4':'你表达的顾虑','Q5':'你报告的生活场景'}[q],
                            'source_question_ids':[q],'source_value':'、'.join(labels[x] for x in ordering)})
    return {'status':'descriptive' if any_answer else 'insufficient','primary_type':None,'additional_types':[],
            'reported_behavior':answers['Q1']['value']['primary'] if answers['Q1']['state']=='answered' else None,
            'cas':unavailable_cas(),'factors':factors,'support_entry_codes':[],
            'missing_items':['分类映射与研究评估方法尚未适配；仅整理所提供答案，不判定依从性类型'],
            'assessment_method_version':None}
