from geoconv_examples.modelnet_40.classifier import ModelNetClf
from geoconv_examples.modelnet_40.dataset import load_preprocessed_modelnet

import tensorflow as tf
import keras_tuner as kt
import os


def hyper_tuning(dataset_path,
                 logging_dir,
                 template_configuration,
                 neighbors_for_lrf,
                 modelnet10=True,
                 gen_info_file=None,
                 batch_size=4,
                 rotation_delta=1,
                 variant="dirac",
                 pooling="avg",
                 isc_layer_conf=None):
    # Create logging dir
    os.makedirs(logging_dir, exist_ok=True)

    n_radial, n_angular, template_radius = template_configuration

    def build_hypermodel(hp):
        # Configure classifier
        imcnn = ModelNetClf(
            neighbors_for_lrf=neighbors_for_lrf,
            n_radial=n_radial,
            n_angular=n_angular,
            template_radius=template_radius,
            isc_layer_conf=isc_layer_conf,
            modelnet10=modelnet10,
            variant=variant,
            rotation_delta=rotation_delta,
            pooling=pooling,
            noise_stddev=hp.Float("noise_stddev", min_value=0., max_value=0.00015),
            l1_reg_strength=hp.Float("L1_reg_coefficient", min_value=0., max_value=1.)
        )

        loss = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True, reduction="sum_over_batch_size")
        opt = tf.keras.optimizers.AdamW(
            learning_rate=tf.keras.optimizers.schedules.ExponentialDecay(
                initial_learning_rate=hp.Float("learning_rate", min_value=0.001, max_value=0.03),
                decay_steps=hp.Int("decay_steps", min_value=4_500, max_value=10_000),
                decay_rate=hp.Float("lr_exp_decay", min_value=0.15, max_value=1.0),
                staircase=False
            ),
            weight_decay=hp.Float("weight_decay", min_value=0.001, max_value=0.01)
        )

        imcnn.compile(optimizer=opt, loss=loss, metrics="accuracy", run_eagerly=True)

        return imcnn

    tuner = kt.BayesianOptimization(
        hypermodel=build_hypermodel,
        objective=kt.Objective(name="val_accuracy", direction="max"),
        max_trials=10_000,
        num_initial_points=10,
        directory=logging_dir,
        project_name="modelnet_40_hyper_tuning",
        tune_new_entries=True,
        allow_new_entries=True
    )

    # Setup datasets
    train_data = load_preprocessed_modelnet(
        dataset_path,
        set_type="train",
        modelnet10=modelnet10,
        gen_info_file=f"{logging_dir}/{gen_info_file}",
        batch_size=batch_size
    )
    test_data = load_preprocessed_modelnet(
        dataset_path,
        set_type="test",
        modelnet10=modelnet10,
        gen_info_file=f"{logging_dir}/test_{gen_info_file}",
        batch_size=batch_size
    )

    # Start hyperparameter tuning
    stop = tf.keras.callbacks.EarlyStopping(monitor="val_accuracy", patience=2, min_delta=0.01)
    tuner.search(x=train_data, validation_data=test_data, epochs=12, callbacks=[stop])

    # Print best hyperparameters
    best_hp = tuner.get_best_hyperparameters()[0]
    print("Best hyperparameters:")
    for key, value in best_hp.values.items():
        print(key, value)
