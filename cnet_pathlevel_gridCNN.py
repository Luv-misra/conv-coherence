import tensorflow as tf
import numpy as np
from utilities import cnet_helper
import optparse
import sys
import math


def forward_propagation(X_positive, X_negative, E, mode, print_=False):
    """
    Implements forward propagation of Neural coherence model

    Arguments:
    X_positive -- A Placeholder for positive document
    X_negative -- A Placeholder for negative document
    E -- initialized values for embedding matrix
    mode -- whether we are in training: mode=True or testing: mode=False [Used in Batch Normalization].
    print_ -- Whether size of the variables to be printed

    Returns:
    out_positive -- Coherence Score for positive document
    out_negative -- Coherence Score for negative document
    parameters -- a dictionary of tensors containing trainable parameters

    """

    ## First Layer of NN: Transform each grammatical role in the grid into distributed representation - a real valued vector

    # Shared embedding matrix
    W_embedding = tf.get_variable("W_embedding", initializer=tf.convert_to_tensor(E, tf.float32))

    # Look up layer

    # for positive document
    embedding_positive = tf.nn.embedding_lookup(W_embedding, X_positive)
    # for negative document
    embedding_negative = tf.nn.embedding_lookup(W_embedding, X_negative)


    ## Second Layer of NN: Convolution Layer

    filter_sizes = []
    if opts.filter_list != "":
        for i in opts.filter_list.split(","):
            filter_sizes.append(int(i))
    pooled_outputs_positive = []
    pooled_outputs_negative = []
    for i, w_size in enumerate(filter_sizes):
        filter_shape = [w_size, opts.emb_size, opts.nb_filter]
        regularizer = tf.contrib.layers.l2_regularizer(scale=0.1)  # l2 regularizer for filter
        initializer = tf.contrib.layers.xavier_initializer(seed=opts.seed)
        W_conv_layer_1 = tf.Variable(initializer(filter_shape), name="W_conv_layer_1")
        b_conv_layer_1 = tf.Variable(tf.constant(0.0, shape=[opts.nb_filter]), name="b_conv_layer_1")

        # 1D Convolution for positive document
        conv_layer_1_positive = tf.nn.conv1d(embedding_positive, W_conv_layer_1, stride=1,
                                             padding="VALID")  # embedding and W_conv_layer_1 both are 3D matrix
        conv_layer_1_with_bias_positive = tf.nn.bias_add(conv_layer_1_positive, b_conv_layer_1)
        conv_layer_1_with_bn_positive = tf.layers.batch_normalization(conv_layer_1_with_bias_positive,
                                                                      axis=2,
                                                                      center=True,
                                                                      scale=False,
                                                                      training=(mode == tf.estimator.ModeKeys.TRAIN)
                                                                      )
        h_conv_layer_1_positive = tf.nn.relu(conv_layer_1_with_bn_positive,
                                             name="relu_conv_layer_1_positive")  # Apply nonlinearity

        # 1D Convolution for negative document
        conv_layer_1_negative = tf.nn.conv1d(embedding_negative, W_conv_layer_1, stride=1,
                                             padding="VALID")  # embedding and W_conv_layer_1 both are 3D matrix
        conv_layer_1_with_bias_negative = tf.nn.bias_add(conv_layer_1_negative, b_conv_layer_1)
        conv_layer_1_with_bn_negative = tf.layers.batch_normalization(conv_layer_1_with_bias_negative,
                                                                      axis=2,
                                                                      center=True,
                                                                      scale=False,
                                                                      training=(mode == tf.estimator.ModeKeys.TRAIN)
                                                                      )
        h_conv_layer_1_negative = tf.nn.relu(conv_layer_1_with_bn_negative,
                                             name="relu_conv_layer_1_negative")  # Apply nonlinearity


        ## Third Layer of NN: Pooling Layer

        # maxpooling

        # 1D Pooling for positive document
        m_layer_1_positive_inside = tf.nn.pool(h_conv_layer_1_positive, window_shape=[w_size],
                                        strides=[w_size],
                                        pooling_type='MAX', padding="VALID")
        # 1D Pooling for negative document
        m_layer_1_negative_inside = tf.nn.pool(h_conv_layer_1_negative, window_shape=[w_size],
                                        strides=[w_size],
                                        pooling_type='MAX', padding="VALID")
        pooled_outputs_positive.append(m_layer_1_positive_inside)
        pooled_outputs_negative.append(m_layer_1_negative_inside)
    m_layer_1_positive = tf.concat(pooled_outputs_positive, 1)
    m_layer_1_negative = tf.concat(pooled_outputs_negative, 1)


    ## Fourth Layer of NN: Fully Connected Layer

    # Flatten

    # for positive document
    flatten_positive = tf.contrib.layers.flatten(m_layer_1_positive)
    # for negative document
    flatten_negative = tf.contrib.layers.flatten(m_layer_1_negative)

    # Dropout

    # for positive document
    drop_out_positive = tf.nn.dropout(flatten_positive, keep_prob=opts.dropout_ratio, seed=opts.seed)
    # for negative document
    drop_out_negative = tf.nn.dropout(flatten_negative, keep_prob=opts.dropout_ratio, seed=opts.seed)

    # Coherence Scoring
    dim_coherence = drop_out_positive.shape[1]
    v_fc_layer = tf.get_variable("v_fc_layer", shape=[dim_coherence, 1],
                                 initializer=tf.contrib.layers.xavier_initializer(
                                     seed=opts.seed))  # Weight matrix for final layer
    b_fc_layer = tf.get_variable("b_fc_layer", shape=[1],
                                 initializer=tf.constant_initializer(0.0))  # bias for final layer

    # for positive document
    out_positive = tf.add(tf.matmul(drop_out_positive, v_fc_layer), b_fc_layer)

    # for negative document
    out_negative = tf.add(tf.matmul(drop_out_negative, v_fc_layer), b_fc_layer)

    parameters = {"W_embedding": W_embedding,
                  "W_conv_layer_1": W_conv_layer_1,
                  "b_conv_layer_1": b_conv_layer_1,
                  "v_fc_layer": v_fc_layer,
                  "b_fc_layer": b_fc_layer}

    if (print_):
        print("Layer (type)          Output Shape")
        print("_________________________________________")
        print("\nInputLayer:")
        print("X_positive           ", X_positive.shape)
        print("X_negative           ", X_negative.shape)
        print("\nEmbedding Layer:")
        print("Embedding Matrix     ", W_embedding.shape)
        print("Embedding Positive   ", embedding_positive.shape)
        print("Embedding Negative   ", embedding_negative.shape)
        print("\nConvolution 1D Layer:")
        print("Filter Shape         ", W_conv_layer_1.shape)
        print("Conv Positive        ", h_conv_layer_1_positive.shape)
        print("Conv Negative        ", h_conv_layer_1_negative.shape)
        print("\nMax Pooling 1D Layer:")
        print("MaxPool Positive     ", m_layer_1_positive.shape)
        print("MaxPool Negative     ", m_layer_1_negative.shape)
        print("\nFlatten Layer: ")
        print("Flatten Positive     ", flatten_positive.shape)
        print("Flatten Negative     ", flatten_negative.shape)
        print("\nDropout Layer: ")
        print("Dropout Positive     ", drop_out_positive.shape)
        print("Dropout Negative     ", drop_out_negative.shape)
        print("\nFully Connected Layer:")
        print("FC Positive          ", out_positive.shape)
        print("FC Negative          ", out_negative.shape)

    return out_positive, out_negative, parameters


def ranking_loss(pos, neg):
    """
    Implements the ranking objective.

    Arguments:
    pos -- score for positive document batch
    neg -- score for negative document batch

    Returns:
    Average ranking loss for the batch

    """

    loss = tf.maximum(opts.margin + neg - pos, 0.0)
    # print(loss)
    return tf.reduce_mean(loss)


def mini_batches(X, Y, mini_batch_size=32, shuffle=False):
    """
    Creates a list of minibatches from (X, Y)

    Arguments:
    X -- List of Positive Documents
    Y -- List of Negative Documents
    mini_batch_size -- Size of each mini batch

    Returns:
    list of mini batches from the positive and negative documents.

    """
    m = len(X)
    mini_batches = []

    num_complete_minibatches = int(math.floor(m / mini_batch_size))

    for k in range(0, num_complete_minibatches):
        mini_batch_X = X[k * mini_batch_size: k * mini_batch_size + mini_batch_size]
        mini_batch_Y = Y[k * mini_batch_size: k * mini_batch_size + mini_batch_size]
        mini_batch = (np.asarray(mini_batch_X), np.asarray(mini_batch_Y))
        mini_batches.append(mini_batch)

    # Handling the end case (last mini-batch < mini_batch_size)
    if m % mini_batch_size != 0:
        mini_batch_X = X[num_complete_minibatches * mini_batch_size: m]
        mini_batch_Y = Y[num_complete_minibatches * mini_batch_size: m]
        mini_batch = (np.asarray(mini_batch_X), np.asarray(mini_batch_Y))
        mini_batches.append(mini_batch)

    return mini_batches


def variable_mini_batches(X, Y, f_track, shuffle=False):
    """
    Creates a list of variable length minibatches from (X, Y). This is only for test data.

    Arguments:
    X -- Positive Documents
    Y -- Negative Documents
    f_track -- Size of each mini batches are from this
    shuffle -- whether to shuffle the data before creating minibatches

    Returns:
    list of mini batches from the positive and negative documents.

    """
    m = len(X)
    mini_batches = []

    if (shuffle):
        permutation = list(np.random.permutation(m))
        shuffled_X = X[permutation, :]
        shuffled_Y = Y[permutation, :]
    else:
        shuffled_X = X
        shuffled_Y = Y

    #num_complete_minibatches = math.floor(m / mini_batch_size)

    index = 0

    for docId in range(0, max(f_track) + 1):
        indexes = [i for i, idx in enumerate(f_track) if idx == docId]
        mini_batch_size = len(indexes)

        mini_batch_X = shuffled_X[index: index + mini_batch_size]
        mini_batch_Y = shuffled_Y[index: index + mini_batch_size]
        mini_batch = (mini_batch_X, mini_batch_Y)
        mini_batches.append(mini_batch)

        index += mini_batch_size

    return mini_batches


if __name__ == '__main__':
    parser = optparse.OptionParser("%prog [options]")
    parser.add_option("-g", "--log-file", dest="log_file", help="log file [default: %default]")
    parser.add_option("-d", "--data-dir", dest="data_dir",
                      help="directory containing list of train, test and dev file [default: %default]")
    parser.add_option("-m", "--model-dir", dest="model_dir",
                      help="directory to save the best models [default: %default]")
    parser.add_option("-t", "--max-length", dest="maxlen", type="int",
                      help="maximul length (for fixed size input) [default: %default]")  # input size
    parser.add_option("-f", "--nb_filter", dest="nb_filter", type="int",
                      help="nb of filter to be applied in convolution over words [default: %default]")
    # parser.add_option("-r", "--filter_length",    dest="filter_length", type="int",   help="length of neighborhood in words [default: %default]")
    parser.add_option("-w", "--w_size", dest="w_size", type="int",
                      help="window size length of neighborhood in words [default: %default]")
    parser.add_option("-p", "--pool_length", dest="pool_length", type="int",
                      help="length for max pooling [default: %default]")
    parser.add_option("-e", "--emb-size", dest="emb_size", type="int",
                      help="dimension of embedding [default: %default]")
    parser.add_option("-s", "--hidden-size", dest="hidden_size", type="int",
                      help="hidden layer size [default: %default]")
    parser.add_option("-o", "--dropout_ratio", dest="dropout_ratio", type="float",
                      help="ratio of cells to drop out [default: %default]")
    parser.add_option("-a", "--learning-algorithm", dest="learn_alg",
                      help="optimization algorithm (adam, sgd, adagrad, rmsprop, adadelta) [default: %default]")
    parser.add_option("-b", "--minibatch-size", dest="minibatch_size", type="int",
                      help="minibatch size [default: %default]")
    parser.add_option("-l", "--loss", dest="loss",
                      help="loss type (hinge, squared_hinge, binary_crossentropy) [default: %default]")
    parser.add_option("-n", "--epochs", dest="epochs", type="int", help="nb of epochs [default: %default]")
    parser.add_option("-P", "--permutation", dest="p_num", type="int", help="nb of permutation[default: %default]")
    parser.add_option("-F", "--feats", dest="f_list",
                      help="semantic features using in the model, separate by . [default: %default]")
    parser.add_option("-S", "--seed", dest="seed", type="int", help="seed for random number. [default: %default]")
    parser.add_option("-C", "--margin", dest="margin", type="int",
                      help="margin of the ranking objective. [default: %default]")
    parser.add_option("-M", "--eval_minibatches", dest="eval_minibatches", type="int",
                      help="How often we want to evaluate in an epoch. [default: %default]")
    parser.add_option("-L", "--filter_list", dest="filter_list", help="List of filter sizes in conv layer. [default: %default]")
    parser.set_defaults(
        data_dir="./data/"
        , log_file="log"
        , model_dir="./saved_models/18_02/pathlevel/pathlevel_gridCNN/20_02_pathlevel_gridCNN_epoch_"

        , learn_alg="rmsprop"  # sgd, adagrad, rmsprop, adadelta, adam (default)
        , loss="ranking_loss"  # hinge, squared_hinge, binary_crossentropy (default)
        , minibatch_size=10
        , dropout_ratio=1
        , maxlen=2500
        , epochs=5
        , emb_size=100
        , hidden_size=250
        , nb_filter=150
        , w_size=15
        , pool_length=15
        , p_num=20
        , f_list=""  # "0.1.3"
        , seed=2018
        , margin=6
        , eval_minibatches=100
        , filter_list="15"
    )
    opts, args = parser.parse_args(sys.argv)

    print("**Hyperparameters**")
    print("minibatch_size: ", opts.minibatch_size, "  dropout_ratio: ", opts.dropout_ratio,
          "  maxlen: ", opts.maxlen, "  epochs: ", opts.epochs, "  emb_size: ", opts.emb_size, "  hidden_size: ",
          opts.hidden_size, "  nb_filter: ", opts.nb_filter, "  w_size: ", opts.w_size,
          "  pool_length: ", opts.pool_length, "  p_num: ", opts.p_num, "  seed: ", opts.seed, "  margin: ", opts.margin
          , "  eval_minibatches: ", opts.eval_minibatches, "  filter_list: ", opts.filter_list)
    print("Saved model path: ", opts.model_dir, "\n\n")

    vocabs = ['0', 'S', 'O', 'X', '-']

    np.random.seed(2018)
    E = 0.01 * np.random.uniform(-1.0, 1.0, (len(vocabs), opts.emb_size))
    E[len(vocabs) - 1] = 0


    print("loading entity-grid for pos and neg documents...")

    X_train_1, X_train_0, train_f_track = cnet_helper.load_data_by_branch_new("data/cnet_2500.train",perm_num=opts.p_num, maxlen=opts.maxlen, w_size=opts.w_size, vocabs=vocabs, emb_size=opts.emb_size)

    X_dev_1, X_dev_0, dev_f_track = cnet_helper.load_data_by_branch_new("data/cnet_2500.dev", perm_num=opts.p_num, maxlen=opts.maxlen, w_size=opts.w_size, vocabs=vocabs, emb_size=opts.emb_size)

    X_test_1, X_test_0, test_f_track = cnet_helper.load_data_by_branch_new("data/cnet_2500.test",perm_num=opts.p_num, maxlen=opts.maxlen, w_size=opts.w_size, vocabs=vocabs, emb_size=opts.emb_size)

    print('.....................................')
    print("Num of train pairs: ", len(X_train_1))
    print("Num of dev pairs: ", len(X_dev_1))
    print("Num of test pairs: ", len(X_test_1))
    print('.....................................')

    ## Create Placeholders
    X_positive = tf.placeholder(tf.int32, shape=[None, opts.maxlen])  # Placeholder for positive document
    X_negative = tf.placeholder(tf.int32, shape=[None, opts.maxlen])  # Placeholder for negative document
    mode = tf.placeholder(tf.bool, name='mode')  # Placeholder needed for batch normalization

    # Forward propagation
    score_positive, score_negative, parameters = forward_propagation(X_positive, X_negative, E, mode, print_=True)

    # Cost function:
    cost = ranking_loss(score_positive, score_negative)

    ## Using keras RMSProp

    W_embedding = parameters["W_embedding"]
    W_conv_layer_1 = parameters["W_conv_layer_1"]
    b_conv_layer_1 = parameters["b_conv_layer_1"]
    v_fc_layer = parameters["v_fc_layer"]
    b_fc_layer = parameters["b_fc_layer"]
    optimizer = tf.keras.optimizers.RMSprop().get_updates(cost,
                                                          [W_embedding, W_conv_layer_1, b_conv_layer_1, v_fc_layer,
                                                           b_fc_layer])

    wins = tf.greater(score_positive, score_negative)
    positive_score = tf.reduce_sum(tf.cast(wins, tf.int32))
    losses = tf.less(score_positive, score_negative)
    negative_score = tf.reduce_sum(tf.cast(losses, tf.int32))

    init = tf.global_variables_initializer()
    m = len(X_train_1)

    with tf.Session() as sess:
        saver = tf.train.Saver()
        best_accuracy = 0.820
        best_epoch = -1
        best_minibatch = -1
        sess.run(init)

        for epoch in range(opts.epochs):
            # randomly shuffle the training data
            np.random.seed(opts.seed)
            np.random.shuffle(X_train_1)
            np.random.seed(opts.seed)
            np.random.shuffle(X_train_0)
            minibatch_cost = 0.
            num_minibatches = int(
                m / opts.minibatch_size)  # number of minibatches of size minibatch_size in the train set
            # minibatches = random_mini_batches(X_train_1, X_train_0, opts.minibatch_size)
            minibatches_train  = mini_batches(X_train_1, X_train_0, opts.minibatch_size)
            print("\n\nStarting epoch: ", epoch)
            print("Number of minibatches: ", len(minibatches_train))
            print("\n\n")

            for (i, minibatch) in enumerate(minibatches_train):

                (minibatch_X_positive, minibatch_X_negative) = minibatch

                _, temp_cost, pos, neg = sess.run([optimizer, cost, score_positive, score_negative],
                                                  feed_dict={X_positive: minibatch_X_positive,
                                                             X_negative: minibatch_X_negative,
                                                             mode: True})
                if ((i + 1) % opts.eval_minibatches) == 0 or i == num_minibatches-1:

                    # """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
                    ########################Test on Dev Data Begins#####################################################
                    wins_count = 0
                    ties_count = 0
                    losses_count = 0

                    minibatches_dev = variable_mini_batches(X_dev_1, X_dev_0, dev_f_track)
                    for (j, minibatch_dev) in enumerate(minibatches_dev):
                        (minibatch_X_positive, minibatch_X_negative) = minibatch_dev

                        pos_score, neg_score = sess.run([positive_score, negative_score],
                                                                  feed_dict={X_positive: minibatch_X_positive,
                                                                             X_negative: minibatch_X_negative,
                                                                             mode: False})
                        if(pos_score>neg_score):
                            wins_count += 1
                        elif(pos_score==neg_score):
                            ties_count += 1
                        else:
                            losses_count += 1

                    recall = wins_count / (wins_count + ties_count + losses_count)
                    precision = wins_count / (wins_count + losses_count)
                    f1 = 2 * precision * recall / (precision + recall)
                    accuracy = wins_count / (wins_count + ties_count + losses_count)

                    if (accuracy > best_accuracy):
                        best_accuracy = accuracy
                        best_epoch = epoch
                        best_minibatch = i
                        name = opts.model_dir + str(epoch) + "_minibatch_" + str(i)
                        saver.save(sess, name)

                    print("\n\n")
                    print("***********Epoch: ", epoch, "    Minibatch: ", i, "  ******************")
                    print("**Best so far** Epoch: ", best_epoch, "    Minibatch: ", best_minibatch, "Accuracy: ", best_accuracy, " **\n")
                    print("##Dev Data set##")
                    print("Wins: ", wins_count)
                    print("Ties: ", ties_count)
                    print("losses: ", losses_count)
                    print(" -Dev Accuracy:", accuracy)
                    print(" -Dev F1 Score:", f1)

                    ########################Test on Dev Data Ends#####################################################
