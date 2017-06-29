import sys
import tensorflow as tf
import numpy as np
import pprint
import argparse
import datetime
import random
import copy

from model import Basic
from mpcm import MPCM
from ql_mpcm import QL_MPCM
from time import gmtime, strftime
from dataset import read_data, build_dict, load_glove, preprocess
from run import train, test

flags = tf.app.flags
flags.DEFINE_integer('train_epoch', 100, 'Training epoch')
flags.DEFINE_integer('test_epoch', 1, 'Test for every n training epoch')
flags.DEFINE_integer("batch_size", 64, "Size of batch (32)")
flags.DEFINE_integer("dim_perspective", 10, "Maximum number of perspective (20)")
flags.DEFINE_integer("dim_embed_word", 300, "Dimension of word embedding (300)")
flags.DEFINE_integer("dim_rnn_cell", 40, "Dimension of RNN cell (100)")
flags.DEFINE_integer("dim_hidden", 100, "Dimension of hidden layer")
flags.DEFINE_integer("num_paraphrase", 1, "Maximum number of question paraphrasing")
flags.DEFINE_integer("rnn_layer", 1, "Layer number of RNN ")
flags.DEFINE_integer("context_maxlen", 0, "Predefined context max length")
flags.DEFINE_integer("validation_cnt", 10, "Number of model validation")
flags.DEFINE_float("rnn_dropout", 0.5, "Dropout of RNN cell")
flags.DEFINE_float("hidden_dropout", 0.5, "Dropout rate of hidden layer")
flags.DEFINE_float("embed_dropout", 0.9, "Dropout rate of embedding layer")
flags.DEFINE_float("learning_rate", 1e-4, "Learning rate of the optimzier")
flags.DEFINE_float("decay_rate", 1.00, "Decay rate of learning rate (0.99)")
flags.DEFINE_float("decay_step", 100, "Decay step of learning rate")
flags.DEFINE_float("max_grad_norm", 5.0, "Maximum gradient to clip")
flags.DEFINE_boolean("embed_trainable", False, "True to optimize embedded words")
flags.DEFINE_boolean("test", False, "True to run only iteration 5")
flags.DEFINE_boolean("debug", False, "True to show debug message")
flags.DEFINE_boolean("save", False, "True to save model after testing")
flags.DEFINE_boolean("sample_params", True, "True to sample parameters")
flags.DEFINE_string("model", "m", "b: basic, m: mpcm, q: ql_mpcm")
flags.DEFINE_string('train_path', './data/train-v1.1.json', 'Training dataset path')
flags.DEFINE_string('dev_path', './data/dev-v1.1.json',  'Development dataset path')
flags.DEFINE_string('pred_path', './result/dev-v1.1-pred.json', 'Prediction output path')
flags.DEFINE_string('glove_path', \
        '~/common/glove/glove.6B.'+ str(tf.app.flags.FLAGS.dim_embed_word) +'d.txt', 'embed path')
flags.DEFINE_string('checkpoint_dir', './result/ckpt/', 'Checkpoint directory')
FLAGS = flags.FLAGS


def run(model, params, train_dataset, dev_dataset):
    max_em = max_f1 = max_point = 0
    train_epoch = params['train_epoch']
    test_epoch = params['test_epoch']

    for epoch_idx in range(train_epoch):
        start_time = datetime.datetime.now()
        print("\nEpoch %d" % (epoch_idx + 1))
        train(model, train_dataset, epoch_idx + 1, params)
        elapsed_time = datetime.datetime.now() - start_time
        print('Traning Done', elapsed_time)
        
        if (epoch_idx + 1) % test_epoch == 0:
            f1, em, loss = test(model, dev_dataset, params)
            if params['save']:
                model.save(params['checkpoint_dir'], epoch_idx+1)

            if max_f1 > f1 - 5e-1 and epoch_idx > 0:
                print('Max f1: %.3f, em: %.3f, epoch: %d' % (max_f1, max_em, max_point))
                print('Early stopping')
                break
            else:
                max_point = max_point if max_em > em else epoch_idx 
                max_em = max_em if max_em > em else em 
                max_f1 = max_f1 if max_f1 > f1 else f1
                print('Max f1: %.3f, em: %.3f, epoch: %d' % (max_f1, max_em, max_point))
    
    model.reset_graph()


def sample_parameters(params):
    params['learning_rate'] = float('%.6f' % (random.uniform(1e-5, 1e-2)))
    params['dim_rnn_cell'] = random.randint(1, 10) * 10 

    return params


def main(_):
    # Parse arguments and flags
    expected_version = '1.1'
    saved_params = FLAGS.__flags

    # Load dataset once
    train_path = saved_params['train_path']
    dev_path = saved_params['dev_path']
    train_dataset = read_data(train_path, expected_version)
    dev_dataset = read_data(dev_path, expected_version)
    
    """
    Dataset is structured in json format:
        articles (list)
        - paragraphs (list)
            - context
            - qas (list)
                - answers
                - question
                - id 
        - title
    """
    # Preprocess dataset
    dictionary, _, c_maxlen, q_maxlen = build_dict(train_dataset, saved_params)
    pretrained_glove, dictionary = load_glove(dictionary, saved_params)
    if saved_params['context_maxlen'] > 0: 
        c_maxlen = saved_params['context_maxlen']

    train_dataset = preprocess(train_dataset, dictionary, c_maxlen, q_maxlen)
    dev_dataset = preprocess(dev_dataset, dictionary, c_maxlen, q_maxlen)
    saved_params['context_maxlen'] = c_maxlen
    saved_params['question_maxlen'] = q_maxlen
    saved_params['voca_size'] = len(dictionary)
    saved_params['dim_output'] = c_maxlen

    for model_idx in range(saved_params['validation_cnt']):
        # Copy params, ready for validation
        if saved_params['sample_params']:
            params = sample_parameters(copy.deepcopy(saved_params))
        else:
            params = copy.deepcopy(saved_params)
        print('\nModel_%d paramter set' % (model_idx))
        pprint.PrettyPrinter().pprint(params)

        # Make model and run experiment
        if params['model'] == 'm':
            my_model = MPCM(params, initializer=[pretrained_glove, dictionary])
        elif params['model'] == 'q':
            my_model = QL_MPCM(params, initializer=[pretrained_glove, dictionary])
        elif params['model'] == 'b':
            my_model = Basic(params, initializer=[pretrained_glove, dictionary])
        else:
            assert False, "Check your version %s" % params['model']
        run(my_model, params, train_dataset, dev_dataset) 


if __name__ == '__main__':
    tf.app.run()

