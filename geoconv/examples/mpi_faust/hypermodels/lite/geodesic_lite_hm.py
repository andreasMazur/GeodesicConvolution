from geoconv.layers.conv_geodesic import ConvGeodesic
from geoconv.models.intrinsic_model import ImCNN

from tensorflow import keras

import keras_tuner
import gc


class GeodesicLiteHyperModel(keras_tuner.HyperModel):

    def __init__(self,
                 signal_dim,
                 kernel_size,
                 amt_target_nodes,
                 amt_convolutions,
                 amt_splits,
                 amt_gradient_splits,
                 kernel_radius,
                 batch_normalization=True,
                 output_dim=128):
        super().__init__()
        self.signal_dim = signal_dim
        self.kernel_size = kernel_size
        self.kernel_radius = kernel_radius
        self.amt_target_nodes = amt_target_nodes
        self.amt_convolutions = amt_convolutions
        self.amt_splits = amt_splits
        self.amt_gradient_splits = amt_gradient_splits
        self.batch_normalization = batch_normalization
        self.output_dim = output_dim

    def build(self, hp):
        keras.backend.clear_session()
        gc.collect()

        signal_input = keras.layers.Input(shape=self.signal_dim, name="signal")
        bc_input = keras.layers.Input(shape=(self.kernel_size[0], self.kernel_size[1], 3, 2), name="bc")

        signal = ConvGeodesic(
            output_dim=self.output_dim,
            amt_templates=1,
            template_radius=self.kernel_radius,
            activation="relu",
            splits=self.amt_splits,
            name="gc_0",
            variant="lite"
        )([signal_input, bc_input])

        if self.batch_normalization:
            signal = keras.layers.BatchNormalization(axis=-1)(signal)
        for idx in range(1, self.amt_convolutions):
            signal = ConvGeodesic(
                output_dim=self.output_dim,
                amt_templates=1,
                template_radius=self.kernel_radius,
                activation="relu",
                splits=self.amt_splits,
                name=f"gc_{idx}",
                variant="lite"
            )([signal, bc_input])

            if self.batch_normalization:
                signal = keras.layers.BatchNormalization(axis=-1)(signal)

        output = keras.layers.Dense(self.amt_target_nodes)(signal)

        model = ImCNN(
            splits=self.amt_gradient_splits,
            inputs=[signal_input, bc_input],
            outputs=[output]
        )
        loss = keras.losses.SparseCategoricalCrossentropy(from_logits=True)
        opt = keras.optimizers.Adam(learning_rate=hp.Float("lr", min_value=1e-4, max_value=1e-2))
        model.compile(optimizer=opt, loss=loss, metrics=["sparse_categorical_accuracy"])

        return model
