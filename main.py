
import re
import uuid
import random
import json
import asyncio

from tqdm import tqdm

import pandas as pd

import openai


#####
#
#   JSON
#
#####


def write_jsonl(path, items):
    with open(path, 'w') as file:
        for item in items:
            file.write(json.dumps(item, ensure_ascii=False))
            file.write('\n')


def read_jsonl(path):
    with open(path) as file:
        for line in file:
            yield json.loads(line)


######
#
#   UID
#
#####


def gen_uid():
    return str(uuid.uuid4())


########
#
#   DOTENV
#
#######


def read_dotenv(path):
    with open(path) as file:
        for line in file:
            if '=' in line:
                yield line.rstrip('\n').split('=', 1)


#####
#
#   VICUNA
#
#######


# {'question_id': 1,
#  'text': 'How can I improve my time management skills?',
#  'category': 'generic'}


def parse_vicuna(items):
    for item in items:
        yield {
            'id': gen_uid(),
            'source': 'vicuna',
            'source_id': item['question_id'],
            'category': item['category'],
            'instruction': item['text']
        }


######
#
#   ALPACA
#
######


# {'id': 'user_oriented_task_0',
#  'motivation_app': 'Grammarly',
#  'instruction': 'The sentence you are given might be too wordy, complicated, or unclear. Rewrite the sentence and make your writing clearer by keeping it concise. Whenever possible, break complex sentences into multiple sentences and eliminate unnecessary words.',
#  'instances': [{'input': 'If you have any questions about my rate or if you find it necessary to increase or decrease the scope for this project, please let me know.',
#    'output': "If you have any questions about my rate or find it necessary to increase or decrease this project's scope, please let me know."}]}


def parse_alpaca(items):
    for item in items:

        instruction = item['instruction']
        input = item['instances'][0]['input']
        if input:
            instruction += f'\n\n"{input}"'

        yield {
            'id': gen_uid(),
            'source': 'alpaca',
            'source_id': item['id'],
            'instruction': instruction
        }


#########
#
#   ARENA
#
######


def parse_arena(records):
    for record in records:
        assert len(record.conversation_a) >= 2
        assert len(record.conversation_b) >= 2
        assert record.conversation_a[0]['role'] == record.conversation_b[0]['role'] == 'user'
        assert record.conversation_a[0]['content'] == record.conversation_b[0]['content']

        yield {
            'id': gen_uid(),
            'source': 'arena',
            'source_id': record.question_id,
            'lang': record.language,
            'instruction': record.conversation_a[0]['content']
        }


########
#
#   OPENAI
#
#####


async def openai_singleturn(
        prompt, model,
        temperature=1,
        max_tokens=None,
        request_timeout=60
):
    completion = await openai.ChatCompletion.acreate(
        model=model,
        messages=[{
            'role': 'user',
            'content': prompt
        }],
        temperature=temperature,
        max_tokens=max_tokens,
        request_timeout=request_timeout
    )
    return completion.choices[0].message.content


#######
#
#   TRANSLATE
#
######


async def openai_translate(instruction):
    prompt = f'''Ты профессиональный переводчик с английского на русский.
Переведи задание для ассистента на русский. Обращайся к ассистенту на ты.

Задание на английском (заключено в [[ ]]):
[[{instruction}]]

Задание на русском:'''
    answer = await openai_singleturn(prompt, model='gpt-3.5-turbo-0613')
    return re.sub(r'\[\[+|\]\]+', '', answer).strip()


async def openai_translate_worker(items):
    for item in items:
        try:
            item['answer'] = await openai_translate(item['instruction'])
        except openai.error.OpenAIError as error:
            print(error, file=sys.stderr)
