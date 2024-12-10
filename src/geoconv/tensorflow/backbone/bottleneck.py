from geoconv.tensorflow.backbone.resnet_block import ResNetBlock
from geoconv.tensorflow.layers.barycentric_coordinates import BarycentricCoordinates

import tensorflow as tf


class Bottleneck(tf.keras.layers.Layer):
    def __init__(self,
                 amount_vertices,
                 init_conv_dim,
                 n_radial,
                 n_angular,
                 neighbors_for_lrf,
                 template_radius,
                 noise_stddev,
                 rotation_delta,
                 variant,
                 initializer):
        super().__init__()

        self.amount_vertices = amount_vertices

        # Init barycentric coordinates layer
        self.bc_layer = BarycentricCoordinates(
            n_radial=n_radial, n_angular=n_angular, neighbors_for_lrf=neighbors_for_lrf
        )
        self.bc_layer.adapt(template_radius=template_radius)

        # Add noise during training
        self.noise = tf.keras.layers.GaussianNoise(stddev=noise_stddev)

        # Remember parameters for 'init_conv'
        self.init_conv = None
        self.init_conv_dim = init_conv_dim
        self.template_radius = template_radius
        self.rotation_delta = rotation_delta
        self.variant = variant
        self.initializer = initializer

        # Define down-projection layer
        self.down_projection = ResNetBlock(
            amt_templates=1,
            template_radius=self.template_radius,
            rotation_delta=self.rotation_delta,
            conv_type=self.variant,
            activation="relu",
            input_dim=self.init_conv_dim,
            initializer=self.initializer
        )

    def build(self, input_shape):
        _, signal_shape = input_shape

        self.init_conv = ResNetBlock(
            amt_templates=self.init_conv_dim,
            template_radius=self.template_radius,
            rotation_delta=self.rotation_delta,
            conv_type=self.variant,
            activation="relu",
            input_dim=signal_shape[-1],
            initializer=self.initializer
        )

    @tf.function(jit_compile=True)
    def call(self, inputs, training=False, **kwargs):
        coordinates, signal = inputs

        # Compute barycentric coordinates from 3D coordinates
        bc = self.bc_layer(coordinates)

        # Add noise
        signal = self.noise(signal, training=training)

        # Initial convolution
        return_signal = self.init_conv([signal, bc], training=training)

        # Down-projection
        signal = self.down_projection([return_signal, bc])
        indices = tf.map_fn(
            lambda s: tf.math.top_k(tf.squeeze(s[:, 0]), k=self.amount_vertices)[1],
            signal,
            fn_output_signature=tf.int32
        )

        # Gather new coordinates and signals
        new_coordinates = tf.gather(coordinates, indices, batch_dims=1)
        new_signal = tf.gather(tf.concat([return_signal, signal], axis=-1), indices, batch_dims=1)

        return new_coordinates, new_signal