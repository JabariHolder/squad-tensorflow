import tensorflow as tf
import os

from ops import *


class RNN(object):
    def __init__(self, params, initializer):

        # session settings
        config = tf.ConfigProto(device_count={'GPU':1})
        config.gpu_options.allow_growth = True
        config.gpu_options.per_process_gpu_memory_fraction = 0.5
        self.session = tf.Session(config=config)
        self.params = params
        self.model_name = params['model_name']

        # hyper parameters
        self.learning_rate = params['learning_rate']
        self.decay_rate = params['decay_rate']
        self.decay_step = params['decay_step']
        self.min_grad = params['min_grad']
        self.max_grad = params['max_grad']

        # rnn parameters
        self.max_question_len = params['max_question_len']
        self.max_passage_len = params['max_passage_len']
        self.max_answer_len = params['max_answer_len']
        self.cell_layer_num = params['lstm_layer']
        self.dim_question = params['dim_question'] 
        self.dim_passage = params['dim_passage'] 
        self.dim_embed_word = params['dim_embed_word']
        self.dim_hidden = params['dim_hidden']
        self.dim_rnn_cell = params['dim_rnn_cell']
        self.dim_output = params['dim_output']
        self.embed = params['embed']
        self.embed_trainable = params['embed_trainable']
        self.checkpoint_dir = params['checkpoint_dir']
        self.initializer = initializer

        # input data placeholders
        self.question = tf.placeholder(tf.int32, [None, self.max_question_len])
        self.passage = tf.placeholder(tf.int32, [None, self.max_passage_len])
        self.answer = tf.placeholder(tf.int32, [None])
        self.len_question = tf.placeholder(tf.int32, [None])
        self.len_passage = tf.placeholder(tf.int32, [None])
        self.len_answer = tf.placeholder(tf.int32, [None])
        self.lstm_dropout = tf.placeholder(tf.float32)
        self.hidden_dropout = tf.placeholder(tf.float32)

        # model settings
        self.global_step = tf.Variable(0, name="step", trainable=False)
        self.learning_rate = tf.train.exponential_decay(
                self.learning_rate, self.global_step,
                self.decay_step, self.decay_rate, staircase=True)
        self.optimizer = tf.train.AdamOptimizer(self.learning_rate)
        self.optimize = None
        self.saver = None
        self.losses = None
        self.logits = None

        # model build
        self.merged_summary = None
        self.embed_writer = tf.summary.FileWriter(self.checkpoint_dir)
        self.embed_config = projector.ProjectorConfig()
        self.projector = None
        self.build_model()
        self.session.run(tf.global_variables_initializer())
       
        # debug initializer
        '''
        with tf.variable_scope('Unigram', reuse=True):
            unigram_embed = tf.get_variable("embed", [self.dim_unigram, self.dim_embed_unigram], dtype=tf.float32)
            print(unigram_embed.eval(session=self.session))
        '''

    def encode(self, inputs, length, max_length, dim_input, dim_embed, 
            initializer=None, trainable=True, scope='encoding'):
        with tf.variable_scope(scope) as scope: 
            fw_cell = lstm_cell(self.dim_rnn_cell, self.cell_layer_num, self.lstm_dropout)
            bw_cell = lstm_cell(self.dim_rnn_cell, self.cell_layer_num, self.lstm_dropout)
            
            inputs_embed, self.projector = embedding_lookup(inputs, 
                    dim_input, dim_embed, self.checkpoint_dir, self.embed_config, 
                    draw=True, initializer=initializer, trainable=trainable, scope=scope)
            inputs_reshape = rnn_reshape(inputs_embed, dim_embed, max_length) 
            outputs = rnn_model(inputs_reshape, length, max_length, fw_cell, self.params)
            return outputs


    def build_model(self):
        print("## Building an RNN model")

        question_encoded = self.encode(inputs=self.question,
                length=self.len_question,
                max_length=self.max_question_len,
                dim_input=self.dim_question,
                dim_embed=self.dim_embed_word,
                trainable=self.embed_trainable,
                scope='Question')

        passage_encoded = self.encode(inputs=self.passage,
                length=self.len_passage,
                max_length=self.max_passage_len,
                dim_input=self.dim_passage,
                dim_embed=self.dim_embed_word,
                trainable=self.embed_trainable,
                scope='Passage')
        print('Q', question_encoded)
        print('P', passage_encoded)

        cct = tf.concat(axis=1, values=[question_encoded, question_encoded])

        hidden1 = linear(inputs=cct,
                output_dim=self.dim_hidden,
                dropout_rate=self.hidden_dropout,
                activation=tf.nn.relu,
                scope='Hidden1')

        logits = linear(inputs=hidden1,
            output_dim=self.dim_output, 
            scope='Output')

        self.logits = logits 
        self.losses = tf.reduce_mean(tf.nn.sparse_softmax_cross_entropy_with_logits(logits=logits,
            labels=self.answer))

        tf.summary.scalar('Loss', self.losses)
        self.variables = tf.trainable_variables()

        grads = []
        for grad in tf.gradients(self.losses, self.variables):
            if grad is not None:
                grads.append(tf.clip_by_value(grad, self.min_grad, self.max_grad))
            else:
                grads.append(grad)
        self.optimize = self.optimizer.apply_gradients(zip(grads, self.variables), global_step=self.global_step)

        model_vars = [v for v in tf.global_variables()]
        print('model variables', [model_var.name for model_var in tf.trainable_variables()])
        self.saver = tf.train.Saver(model_vars)
        self.merged_summary = tf.summary.merge_all()

    @staticmethod
    def reset_graph():
        tf.reset_default_graph()

    def save(self, checkpoint_dir, step):
        file_name = "%s.model" % self.model_name
        self.saver.save(self.session, os.path.join(checkpoint_dir, file_name))
        print("Model saved", file_name)

    def load(self, checkpoint_dir):
        file_name = "%s.model" % self.model_name
        file_name += "-10800"
        self.saver.restore(self.session, os.path.join(checkpoint_dir, file_name))
        print("Model loaded", file_name)

