import os
from datetime import datetime

import h5py
import numpy as np

import datagen

from keras.callbacks import ModelCheckpoint, TensorBoard
from keras.layers import Conv2D, Conv2DTranspose
from keras.layers import Input, Reshape, Activation
from keras.models import Model

BATCH_SIZE = 8

FILTER_SIZES = [
    [(9, 9), (5, 5), (3, 3)]
]

NO_FILTERS = [
    [32, 16, 8],
]

# ======================================================================================================================
print "Starting training"

for filter_sizes in FILTER_SIZES:
    for no_filters in NO_FILTERS:
        dt = datetime.now().strftime('%y%m%d_%H%M')

        NETWORK_NAME = "ggcnn_%s_%s_%s__%s_%s_%s" % (filter_sizes[0][0], filter_sizes[1][0], filter_sizes[2][0],
                                                     no_filters[0], no_filters[1], no_filters[2])
        NETWORK_NOTES = """
            Input: Inpainted depth, subtracted mean, in meters, with random rotations and zoom. 
            Output: q, cos(2theta), sin(2theta), grasp_width in pixels/150.
            Filter Sizes: %s
            No Filters: %s
        """ % (
            repr(filter_sizes),
            repr(no_filters)
        )
        OUTPUT_FOLDER = 'data/networks/%s__%s/' % (dt, NETWORK_NAME)

        if not os.path.exists(OUTPUT_FOLDER):
            os.makedirs(OUTPUT_FOLDER)

        # Save the validation data so that it matches this network.
        #np.save(os.path.join(OUTPUT_FOLDER, '_val_input'), x_test)

        # ====================================================================================================
        # Network

        input_layer = Input(shape=datagen.OUTPUT_IMG_SIZE)

        x = Conv2D(no_filters[0], kernel_size=filter_sizes[0], strides=(3, 3), padding='same', activation='relu')(input_layer)
        x = Conv2D(no_filters[1], kernel_size=filter_sizes[1], strides=(2, 2), padding='same', activation='relu')(x)
        encoded = Conv2D(no_filters[2], kernel_size=filter_sizes[2], strides=(2, 2), padding='same', activation='relu')(x)

        x = Conv2DTranspose(no_filters[2], kernel_size=filter_sizes[2], strides=(2, 2), padding='same', activation='relu')(encoded)
        x = Conv2DTranspose(no_filters[1], kernel_size=filter_sizes[1], strides=(2, 2), padding='same', activation='relu')(x)
        x = Conv2DTranspose(no_filters[0], kernel_size=filter_sizes[0], strides=(3, 3), padding='same', activation='relu')(x)

        # ===================================================================================================
        # Output layers

        #pos_output = Conv2D(1, kernel_size=2, padding='same', activation='linear', name='pos_out')(x)
        pos_output_class = Conv2D(2, kernel_size=3, padding='same', activation='relu', name='pos_out_class')(x)
        pos_reshaped = Reshape((300*300, 2))(pos_output_class)
        pos_softmax = Activation('softmax')(pos_reshaped)
        cos_output = Conv2D(1, kernel_size=2, padding='same', activation='linear', name='cos_out')(x)
        sin_output = Conv2D(1, kernel_size=2, padding='same', activation='linear', name='sin_out')(x)
        width_output = Conv2D(1, kernel_size=2, padding='same', activation='linear', name='width_out')(x)

        # ===================================================================================================
        # And go!

        ae = Model(input_layer, [pos_softmax, cos_output, sin_output, width_output])
        ae.compile(optimizer='rmsprop', loss=['categorical_crossentropy', 'mean_squared_error', 'mean_squared_error', 'mean_squared_error'])

        ae.summary()

        with open(os.path.join(OUTPUT_FOLDER, '_description.txt'), 'w') as f:
            # Write description to file.
            f.write(NETWORK_NOTES)
            f.write('\n\n')
            ae.summary(print_fn=lambda q: f.write(q + '\n'))

        tb_logdir = './data/tensorboard/%s_%s' % (dt, NETWORK_NAME)

        my_callbacks = [
            TensorBoard(log_dir=tb_logdir),
            ModelCheckpoint(os.path.join(OUTPUT_FOLDER, 'epoch_{epoch:02d}_model.hdf5'), period=1),
        ]

        #train_set, test_set = datagen.get_data_list()
        train_generator = datagen.DataGenerator(batch_size = BATCH_SIZE, train=True)
        #test_generator = datagen.DataGenerator(batch_size = BATCH_SIZE, train=False)

        ae.fit_generator(generator=train_generator,# validation_data=test_generator,
                        use_multiprocessing=True,
                        workers=6,#we have 8 cores, so leave a few open?
                        epochs=100,
                        shuffle=True,
                        callbacks=my_callbacks,
                        #validation_data=(x_test, y_test)
                        )
