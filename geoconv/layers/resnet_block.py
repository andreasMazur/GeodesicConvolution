from tensorflow.keras.layers import Layer, Add, BatchNormalization, Activation

from geoconv.layers.geodesic_conv import ConvGeodesic
from geoconv.layers.angular_max_pooling import AngularMaxPooling

import tensorflow as tf


class ResNetBlock(Layer):
    """A ResNet-block of geodesic convolutions

    Careful: This class is experimental!

    Attributes
    ----------
    input_dim:
        The input dimension of the signal.
    amt_kernel:
        The amount of kernels to use in both geodesic convolutions.
    rotation_delta:
        The rotation delta for both geodesic convolutions.
    amt_splits:
        The amount of splits for both geodesic convolutions.
    """

    def __init__(self, input_dim, amt_kernel, rotation_delta, amt_splits):
        super(ResNetBlock, self).__init__()

        self.amt_kernel = amt_kernel
        self.rotation_delta = rotation_delta
        self.amt_splits = amt_splits
        self.input_dim = input_dim

        self.geoconv_1 = ConvGeodesic(
            output_dim=input_dim,
            amt_kernel=self.amt_kernel,
            activation="relu",
            rotation_delta=self.rotation_delta,
            splits=self.amt_splits
        )
        self.bn_1 = BatchNormalization()

        self.geoconv_2 = ConvGeodesic(
            output_dim=input_dim,
            amt_kernel=self.amt_kernel,
            activation="relu",
            rotation_delta=self.rotation_delta,
            splits=self.amt_splits
        )
        self.bn_2 = BatchNormalization()

        self.amp = AngularMaxPooling()

        self.add = Add()
        self.activation = Activation("relu")

    @tf.function
    def call(self, inputs):
        signal_input, barycentric = inputs

        signal = self.geoconv_1([signal_input, barycentric])
        signal = self.amp(signal)
        signal = self.bn_1(signal)
        # signal = self.activation(signal)

        signal = self.geoconv_2([signal, barycentric])
        signal = self.amp(signal)
        signal = self.bn_2(signal)
        # signal = self.activation(signal)

        signal = self.add([signal, signal_input])
        return signal

    def get_config(self):
        config = super(ResNetBlock, self).get_config()
        config.update({
            "amt_kernel": self.amt_kernel,
            "rotation_delta": self.rotation_delta,
            "amt_splits": self.amt_splits,
            "input_dim": self.input_dim
        })
        return config