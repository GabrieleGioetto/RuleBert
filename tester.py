# IMPORTS

import torch
import json
from torch.utils.data import TensorDataset
from torch.utils.data import DataLoader, SequentialSampler
from torch.nn import CrossEntropyLoss
from tqdm import tqdm
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import time
from data_generation import format_time, flat_accuracy, confidence_accuracy
import numpy as np
import argparse
from datetime import datetime

my_parser = argparse.ArgumentParser(description='Test Model')


my_parser.add_argument('--test_data_dir',
                       type=str,
                       help='path to test data')

my_parser.add_argument('--model_dir',
                       type=str,
                       help='path to model')

my_parser.add_argument('--max_length',
                       type=int,
                       default=512,
                       help='max length for tokenization')

my_parser.add_argument('--batch_size',
                       type=int,
                       default=16,
                       help='batch size')

my_parser.add_argument('--hard_rule',
                       action='store_true',
                       default=False,
                       help='Hard Rule')

my_parser.add_argument('--verbose',
                       action='store_true',
                       default=False,
                       help='Verbose Output')

args = my_parser.parse_args()

test_file_dir = args.test_data_dir  # 'test_data/test.json'
model_path = args.model_dir  # 'model/'
max_length = args.max_length  # 512
batch_size = args.batch_size  # 16
hard_rule = args.hard_rule  # False
verbose = args.verbose

# LOAD DATA
test_file = test_file_dir + 'test.jsonl'
test_theories = [json.loads(jline) for jline in open(test_file, "r").read().splitlines()]

# prepare training data
test_context = [t['context'] for t in test_theories]
test_hypotheses = [t['hypothesis_sentence'] for t in test_theories]
test_labels_ = [1 if t['output'] else 0 for t in test_theories]
if not hard_rule:
    test_data_weights_ = [t['hyp_weight'] for t in test_theories]

# Load tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_path)


# tokenize training data
test_input_ids_ = []
test_attention_masks_ = []

for c, h in tqdm(zip(test_context, test_hypotheses)):
    encoded = tokenizer.encode_plus(c, h,
                                    max_length=max_length,
                                    truncation=True,
                                    return_tensors='pt',
                                    padding='max_length')
    test_input_ids_.append(encoded['input_ids'])
    test_attention_masks_.append(encoded['attention_mask'])

test_input_ids = torch.cat(test_input_ids_, dim=0)
test_attention_masks = torch.cat(test_attention_masks_, dim=0)

test_labels = torch.tensor(test_labels_)
if not hard_rule:
    test_data_weights = torch.tensor(test_data_weights_)

if not hard_rule:

    test_dataset = TensorDataset(test_input_ids, test_attention_masks, test_labels, test_data_weights)
else:
    test_dataset = TensorDataset(test_input_ids, test_attention_masks, test_labels)

test_dataloader = DataLoader(dataset=test_dataset,
                             sampler=SequentialSampler(test_dataset),
                             batch_size=batch_size,
                             )

# Load model
device = torch.device("cuda") if torch.cuda.is_available() else torch.device('cpu')

model = AutoModelForSequenceClassification.from_pretrained(model_path)
model = model.to(device)

test_stats = []
t0 = time.time()
model.eval()
total_test_accuracy = 0
total_test_loss = 0.0
total_conf_acc = 0

all_probs = []
all_diff = []
all_logits = []

loss_fct = CrossEntropyLoss(reduction='none')
for batch in tqdm(test_dataloader):

    b_input_ids = batch[0].to(device)
    b_input_mask = batch[1].to(device)
    b_labels = batch[2].to(device)
    if not hard_rule:
        b_weights = batch[3].to(device)

    with torch.no_grad():
        if not hard_rule:
            o = model(b_input_ids, attention_mask=b_input_mask)
        else:
            o = model(b_input_ids, 
                          attention_mask=b_input_mask, 
                          labels=b_labels)


    logits = o.logits


    if not hard_rule:
        loss = torch.mean(loss_fct(logits.view(-1, 2), b_labels.view(-1)) * b_weights)
    else:
        loss = o.loss
    total_test_loss += loss.item()

    logits = logits.detach().cpu().numpy()
    label_ids = b_labels.to('cpu').numpy()

    all_logits = all_logits + logits.tolist()


    total_test_accuracy += flat_accuracy(logits, label_ids)
    if not hard_rule:
        probs, diff = confidence_accuracy(logits, b_labels, b_weights, verbose=verbose)
        all_probs.extend(probs.tolist())
        all_diff.extend(diff.tolist())
avg_test_accuracy = total_test_accuracy / len(test_dataloader)

print("  Accuracy: {}".format(avg_test_accuracy))

avg_test_loss = total_test_loss / len(test_dataloader)

test_time = format_time(time.time() - t0)

print("  Validation Loss: {0:.2f}".format(avg_test_loss))
print("  Validation took: {:}".format(test_time))

test_stats.append(
    {
        'Test. Loss': avg_test_loss,
        'Test. Accur.': avg_test_accuracy,
        'Test Time': test_time
    }
)


print("")
print("Testing complete!")

print("Total testing took {:} (h:mm:ss)".format(test_time))

results = []

for logit, context, hypotheses, label, prob in zip(all_logits, test_context, test_hypotheses, test_labels_, all_probs):
    predicted_value = 0 if logit[0] > logit[1] else 1
    confidence = prob[predicted_value]
    results.append({
        "Context": context,
        "hypotheses": hypotheses,
        "label (true value)": label,
        "predicted value": predicted_value,
        "confidence (minimum confidence 0.5)": confidence
    })

test_stats.append({'test_data_dir': test_file_dir,
                'max_length': max_length,
                'batch_size': batch_size})

if not hard_rule:
    test_stats.append({'probs': all_probs,
                    'diff': all_diff})

    diffs = np.array(test_stats[2]['diff'])
    ca_001 = sum(diffs < 0.01) / len(diffs)
    ca_005 = sum(diffs < 0.05) / len(diffs)
    ca_01 = sum(diffs < 0.1) / len(diffs)
    ca_015 = sum(diffs < 0.15) / len(diffs)

    test_stats[0]['CA@0.01'] = ca_001
    test_stats[0]['CA@0.05'] = ca_005
    test_stats[0]['CA@0.1'] = ca_01
    test_stats[0]['CA@0.15'] = ca_015

json.dump(test_stats, open(f"{test_file_dir}test_stats.json", "w"), indent=4)
json.dump(results, open(f"{test_file_dir}results_{datetime.now().strftime('%d%m%Y_%H:%M:%S')}.json", "w"), indent=4)
