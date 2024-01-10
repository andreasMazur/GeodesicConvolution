from geoconv.layers.angular_max_pooling import AngularMaxPooling
from geoconv.layers.conv_dirac import ConvDirac
from geoconv.models.intrinsic_model import ImCNN

import tensorflow as tf


class Imcnn(ImCNN):
    def __init__(self, template_radius, rotations, splits):
        super().__init__(splits=splits, rotations=rotations)
        self.amp = AngularMaxPooling()
        self.conv1 = ConvDirac(
            amt_templates=96,
            template_radius=template_radius,
            activation="relu",
            name="ISC_layer_1",
            splits=splits
        )
        self.conv2 = ConvDirac(
            amt_templates=256,
            template_radius=template_radius,
            activation="relu",
            name="ISC_layer_2",
            splits=splits,
        )
        self.conv3 = ConvDirac(
            amt_templates=384,
            template_radius=template_radius,
            activation="relu",
            name="ISC_layer_3",
            splits=splits,
        )
        self.conv4 = ConvDirac(
            amt_templates=384,
            template_radius=template_radius,
            activation="relu",
            name="ISC_layer_4",
            splits=splits,
        )
        self.conv5 = ConvDirac(
            amt_templates=256,
            template_radius=template_radius,
            activation="relu",
            name="ISC_layer_5",
            splits=splits
        )
        self.output_layer = tf.keras.layers.Dense(6890)

    def call(self, inputs, orientation=tf.constant(-1), training=None, mask=None):
        signal, bc = inputs
        signal = self.conv1([signal, bc], orientation)
        signal = self.amp(signal)
        signal = self.conv2([signal, bc], orientation)
        signal = self.amp(signal)
        signal = self.conv3([signal, bc], orientation)
        signal = self.amp(signal)
        signal = self.conv4([signal, bc], orientation)
        signal = self.amp(signal)
        signal = self.conv5([signal, bc], orientation)
        signal = self.amp(signal)
        return self.output_layer(signal)
