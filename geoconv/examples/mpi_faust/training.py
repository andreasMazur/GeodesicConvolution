from tensorflow.keras import Input
from tensorflow.keras.layers import Dense, Normalization, Dropout

from geoconv.geodesic_conv import ConvGeodesic
from geoconv.examples.mpi_faust.tf_dataset import load_preprocessed_faust, faust_mean_variance

import tensorflow as tf


def define_model(signal_shape,
                 bc_shape,
                 output_dim,
                 dataset_mean,
                 dataset_var,
                 lr=.00045,
                 dropout=.2):

    # Define model
    signal_input = Input(shape=signal_shape, name="Signal")
    bary_input = Input(shape=bc_shape, name="Barycentric")

    signal = Normalization(axis=None, mean=dataset_mean, variance=dataset_var)(signal_input)
    signal = Dropout(rate=dropout)(signal)
    signal = ConvGeodesic(output_dim=116, amt_kernel=1, activation="relu")([signal, bary_input])
    signal = ConvGeodesic(output_dim=136, amt_kernel=1, activation="relu")([signal, bary_input])
    logits = Dense(output_dim)(signal)

    model = tf.keras.Model(inputs=[signal_input, bary_input], outputs=[logits])
    loss = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True)
    opt = tf.keras.optimizers.Adam(learning_rate=lr)
    model.compile(optimizer=opt, loss=loss, metrics=["sparse_categorical_accuracy"])
    model.summary()
    return model


def train_on_faust(tf_faust_dataset,
                   tf_faust_dataset_val,
                   batch_size=1,
                   model=None,
                   run=0):

    log_dir = f"./logs/fit/{run}/"
    tensorboard_callback = tf.keras.callbacks.TensorBoard(
        log_dir=log_dir, histogram_freq=1, update_freq="epoch", write_steps_per_second=True, profile_batch=(1, 1000)
    )

    checkpoint_path = f"./training/{run}_cp.ckpt"
    cp_callback = tf.keras.callbacks.ModelCheckpoint(filepath=checkpoint_path, save_freq='epoch', verbose=1)

    model.fit(
        tf_faust_dataset.batch(batch_size).shuffle(5, reshuffle_each_iteration=True),
        epochs=200,
        callbacks=[tensorboard_callback, cp_callback],
        validation_data=tf_faust_dataset_val.batch(batch_size).prefetch(tf.data.AUTOTUNE)
    )


if __name__ == "__main__":
    path_preprocessed_dataset = "../geoconv/examples/mpi_faust/preprocessed_smaller_shot_v4_a8.zip"
    amt_nodes = 6890
    signal_dim = 144
    kernel_size = (2, 8)
    dataset = load_preprocessed_faust(
        path_preprocessed_dataset, amt_nodes, signal_dim, kernel_size=kernel_size
    )
    dataset_val = load_preprocessed_faust(
        path_preprocessed_dataset, amt_nodes, signal_dim, kernel_size=kernel_size, val=True
    )
    faust_mean, faust_var = faust_mean_variance(dataset)
    network = define_model(
        signal_shape=(amt_nodes, signal_dim),
        bc_shape=(amt_nodes, kernel_size[1], kernel_size[0], 3, 2),
        output_dim=amt_nodes,
        dataset_mean=faust_mean,
        dataset_var=faust_var,
        lr=.0047,
        dropout=.0
    )
    train_on_faust(
        tf_faust_dataset=dataset,
        tf_faust_dataset_val=dataset_val,
        batch_size=1,
        model=network,
        run=0,
    )
