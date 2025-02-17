from geoconv_examples.modelnet_40.classifier import ModelNetClf
from geoconv_examples.modelnet_40.dataset import load_preprocessed_modelnet

import os
import sys
import tensorflow as tf


def model_configuration(neighbors_for_lrf,
                        projection_neighbors,
                        n_radial,
                        n_angular,
                        template_radius,
                        modelnet10,
                        variant,
                        pc_pooling_variant,
                        rotation_delta,
                        exp_lambda,
                        shift_angular,
                        isc_layer_conf,
                        down_sample_pc,
                        time,
                        iterations):
    # Define model
    imcnn = ModelNetClf(
        neighbors_for_lrf=neighbors_for_lrf,
        projection_neighbors=projection_neighbors,
        n_radial=n_radial,
        n_angular=n_angular,
        template_radius=template_radius,
        isc_layer_conf=isc_layer_conf,
        down_sample_pc=down_sample_pc,
        modelnet10=modelnet10,
        variant=variant,
        pc_pooling_variant=pc_pooling_variant,
        rotation_delta=rotation_delta,
        azimuth_bins=8,
        elevation_bins=6,
        radial_bins=2,
        histogram_bins=6,
        sphere_radius=0.,
        exp_lambda=exp_lambda,
        shift_angular=shift_angular,
        time=time,
        iterations=iterations
    )

    # Define loss and optimizer
    loss = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True, reduction="sum_over_batch_size")
    opt = tf.keras.optimizers.AdamW(
        learning_rate=tf.keras.optimizers.schedules.ExponentialDecay(
            initial_learning_rate=0.0015218449319544082,
            decay_steps=2461,
            decay_rate=0.76942,
            staircase=False
        ),
        weight_decay=0.019081993138727875
    )

    # Compile the model
    imcnn.compile(optimizer=opt, loss=loss, metrics="accuracy", run_eagerly=True)
    imcnn(tf.random.uniform(shape=[1, 1024, 3]), training=False)
    imcnn.summary()

    return imcnn


def training(dataset_path,
             logging_dir,
             template_configurations=None,
             neighbors_for_lrf=16,
             projection_neighbors=10,
             template_radius=None,
             modelnet10=False,
             gen_info_file=None,
             batch_size=1,
             variant=None,
             pc_pooling_variant=None,
             set_mem_growth=False,
             redirect_output=False,
             rotation_delta=1,
             epochs=200,
             debug=False,
             exp_lambda=2.0,
             shift_angular=True,
             isc_layer_conf=None,
             down_sample_pc=None,
             time=1.,
             iterations=3):
    if isc_layer_conf is None:
        isc_layer_conf = [128, 128, 128, 64]
    if down_sample_pc is None:
        down_sample_pc = [1024, 1024, 512, 256]

    # Create logging dir
    os.makedirs(logging_dir, exist_ok=True)

    # Redirect output (stdout/stderr)
    if redirect_output:
        sys.stdout = open(f"{logging_dir}/stdout.txt", "a")
        sys.stderr = open(f"{logging_dir}/stderr.txt", "a")

    # Set memory growth, e.g., for training multiple models on one GPU
    if set_mem_growth:
        gpus = tf.config.experimental.list_physical_devices('GPU')
        assert len(gpus) > 0, "No GPUs found!"
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)

    # Set filename for generator
    if gen_info_file is None:
        gen_info_file = "generator_info.json"

    for (n_radial, n_angular, template_scale) in template_configurations:
        # Get classification model
        imcnn = model_configuration(
            neighbors_for_lrf=neighbors_for_lrf,
            projection_neighbors=projection_neighbors,
            n_radial=n_radial,
            n_angular=n_angular,
            template_radius=template_radius * template_scale,
            modelnet10=modelnet10,
            variant=variant,
            pc_pooling_variant=pc_pooling_variant,
            rotation_delta=rotation_delta,
            exp_lambda=exp_lambda,
            shift_angular=shift_angular,
            isc_layer_conf=isc_layer_conf,
            down_sample_pc=down_sample_pc,
            time=time,
            iterations=iterations
        )

        # Define callbacks
        exp_number = f"{n_radial}_{n_angular}_{template_scale}"
        csv_file_name = f"{logging_dir}/training_{exp_number}.log"
        csv = tf.keras.callbacks.CSVLogger(csv_file_name)
        stop = tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=10, min_delta=0.01)
        tb = tf.keras.callbacks.TensorBoard(
            log_dir=f"{logging_dir}/tensorboard_{exp_number}",
            histogram_freq=1,
            write_graph=False,
            write_steps_per_second=True,
            update_freq="epoch",
            profile_batch=(1, 200)
        )

        # Load data
        train_data = load_preprocessed_modelnet(
            dataset_path,
            set_type="train",
            modelnet10=modelnet10,
            gen_info_file=f"{logging_dir}/{gen_info_file}",
            batch_size=batch_size,
            debug_data=debug
        )
        test_data = load_preprocessed_modelnet(
            dataset_path,
            set_type="test",
            modelnet10=modelnet10,
            gen_info_file=f"{logging_dir}/test_{gen_info_file}",
            batch_size=batch_size,
            debug_data=debug
        )
        save = tf.keras.callbacks.ModelCheckpoint(
            filepath=f"{logging_dir}/saved_imcnn_{exp_number}",
            monitor="val_loss",
            save_best_only=True,
            save_freq="epoch"
        )

        # Train model
        imcnn.fit(x=train_data, callbacks=[stop, tb, csv, save], validation_data=test_data, epochs=epochs)
