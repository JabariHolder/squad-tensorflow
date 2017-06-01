import tensorflow as tf
import numpy as np

from evaluate import *
from utils import *


def train(model, dataset, params):
    sess = model.session
    batch_size = params['batch_size']
    mini_batch = []
    ground_truths = []
    context_raws = []
    g_norm_list = []
    total_f1 = total_em = total_cnt = 0

    for dataset_idx, dataset_item in enumerate(dataset):
        context = dataset_item['c']
        context_raw = dataset_item['c_raw']
        context_len = dataset_item['c_len']
        for qa in dataset_item['qa']:
            question = qa['q']
            question_len = qa['q_len']
            answer = qa['a']
            answer_start = qa['a_start']
            answer_end = qa['a_end']
            mini_batch.append([context, context_len, question, question_len, answer_start,
                answer_end])
            ground_truths.append(answer)
            context_raws.append(context_raw)
           
            # Run and clear mini-batch
            if (len(mini_batch) == batch_size) or (dataset_idx == len(dataset) - 1):
                batch_context = np.array([b[0] for b in mini_batch])
                batch_context_len = np.array([b[1] for b in mini_batch])
                batch_question = np.array([b[2] for b in mini_batch])
                batch_question_len = np.array([b[3] for b in mini_batch])
                batch_answer_start = np.array([b[4] for b in mini_batch])
                batch_answer_end = np.array([b[5] for b in mini_batch])

                feed_dict = {model.context: batch_context,
                        model.context_len: batch_context_len,
                        model.question: batch_question,
                        model.question_len: batch_question_len,
                        model.answer_start: batch_answer_start,
                        model.answer_end: batch_answer_end,
                        model.rnn_dropout: params['rnn_dropout'],
                        model.hidden_dropout: params['hidden_dropout'],
                        model.embed_dropout: params['embed_dropout']}
                _, loss = sess.run([model.optimize, model.loss], feed_dict=feed_dict)
                
                # Print intermediate result
                if dataset_idx % 5 == 0:
                    """
                    # Dataset Debugging
                    print(batch_context.shape, batch_context_len.shape, batch_question.shape, 
                            batch_question_len.shape, batch_answer_start.shape)
                    for kk in range(len(batch_context)):
                        print('c', batch_context[kk][:10])
                        print('c_len', batch_context_len[kk])
                        print('q', batch_question[kk][:10])
                        print('q_len', batch_question_len[kk])
                        print('a', batch_answer_start[kk])
                        print('a', batch_answer_end[kk])
                    """
                
                    grads, start_logits, end_logits = sess.run(
                            [model.grads, model.start_logits, model.end_logits], 
                            feed_dict=feed_dict)
                    start_idx = np.argmax(start_logits, 1)
                    end_idx = np.argmax(end_logits, 1)
                    predictions = []

                    dprint('', params['debug'])
                    for c, s_idx, e_idx in zip(context_raws, start_idx, end_idx):
                        # dprint('start_idx / end_idx %d/%d'% (s_idx, e_idx), params['debug'])
                        predictions.append(' '.join([w for w in c[s_idx: e_idx+1]]))
                   
                    dprint('shape of grad/sl/el = %s/%s/%s' % (np.asarray(grads).shape, 
                                np.asarray(start_logits).shape, 
                                np.asarray(end_logits).shape), params['debug'])
                    g_norm_group = []
                    for gs in grads:
                        np_gs = np.asarray(gs)
                        g_norm = np.linalg.norm(np_gs)
                        norm_size = np_gs.shape
                        g_norm_group.append(g_norm)
                        dprint('g:' + str(g_norm) + str(norm_size), params['debug'])
                    g_norm_list.append(g_norm_group)

                    for sl, el in zip(start_logits, end_logits):
                        # dprint('s:' + str(sl[:10]), params['debug'])
                        # dprint('e:' + str(el[:10]), params['debug'])
                        pass

                    em = f1 = 0 
                    for prediction, ground_truth in zip(predictions, ground_truths):
                        single_em = metric_max_over_ground_truths(
                                exact_match_score, prediction, ground_truth)
                        single_f1 = metric_max_over_ground_truths(
                                f1_score, prediction, ground_truth)
                        
                        prediction = prediction[:10] if len(prediction) > 10 else prediciton
                        dprint('pred: ' + str(prediction), params['debug'] and (single_f1 > 0))
                        dprint('real: ' + str(ground_truth), params['debug'] and (single_f1 > 0))

                        em += single_em
                        f1 += single_f1
                    
                    dprint('', params['debug'])
                    
                    _progress = progress(dataset_idx / float(len(dataset)))
                    _progress += "loss: %.3f, f1: %.3f, em: %.3f, progress: %d/%d" % (loss, f1 /
                            len(predictions), em / len(predictions), dataset_idx, len(dataset)) 
                    sys.stdout.write(_progress)
                    sys.stdout.flush()
                    
                    if dataset_idx / 5 == 5 and params['test']:
                        sys.exit()

                    total_f1 += f1 / len(predictions)
                    total_em += em / len(predictions)
                    total_cnt += 1
                    
                mini_batch = []
                ground_truths = []
                context_raws = []

    # Average result
    total_f1 /= total_cnt
    total_em /= total_cnt
    print('\nAverage f1: %.3f, em: %.3f' % (total_f1, total_em)) 

    # Write norm information
    if params['debug']:
        f = open('./result/norm_info.txt', 'a')
        f.write('Norm Info\n')
        for g_norm_group in g_norm_list:
            s = '\t'.join([str(g) for g in g_norm_group]) + '\n'
            f.write(s)
        f.close()
    # sys.exit()


def test(model, dataset, params):
    print("loss: %.3f, f1: %.3f, em: %.3f" % (0, 0, 0))

