import sys
import numpy as np

from tensorflow.core.framework import summary_pb2
from evaluate import *

def progress(_progress):
    bar_length = 10  # Modify this to change the length of the progress bar
    status = ""
    if isinstance(_progress, int):
        _progress = float(_progress)
    if not isinstance(_progress, float):
        _progress = 0
        status = "error: progress var must be float\r\n"
    if _progress < 0:
        _progress = 0
        status = "Halt...\r\n"
    if _progress >= 1:
        _progress = 1
        status = "Finished."
    block = int(round(bar_length * _progress))
    text = "\r[%s] %.2f%% %s" % (
            "#" * block + " " * (bar_length-block), _progress * 100, status)

    return text


def dprint(msg, debug, end='\n'):
    if debug:
        print(msg, end=end)


def em_f1_score(predictions, ground_truths, params):
    em = []
    f1 = []
    for prediction, ground_truth in zip(predictions, ground_truths):
        single_em = metric_max_over_ground_truths(
                exact_match_score, prediction, ground_truth)
        single_f1 = metric_max_over_ground_truths(
                f1_score, prediction, ground_truth)
        em.append(single_em)
        f1.append(single_f1)

    em = np.array(em).astype(int)
    f1 = np.array(f1)
    return em, f1


def pred_from_logits(start_logits, end_logits, batch_context_len, c_raws, params):
    start_idx = [np.argmax(sl[:cl], 0) 
            for sl, cl in zip(start_logits, batch_context_len)]
    end_idx = [np.argmax(el[si:cl], 0) + si for el, si, cl in zip(
        end_logits, start_idx, batch_context_len)]

    predictions = []
    for c, s_idx, e_idx in zip(c_raws, start_idx, end_idx):
        predictions.append(' '.join([w for w in c[s_idx: e_idx+1]]))

    return predictions

def write_scalar_summary(name, value, iter, writer):
    value_to_write = summary_pb2.Summary.Value(tag=name, simple_value=value)
    summary = summary_pb2.Summary(value=[value_to_write])
    writer.add_summary(summary, iter)

