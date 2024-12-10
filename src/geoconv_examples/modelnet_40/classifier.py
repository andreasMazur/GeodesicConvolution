from geoconv.tensorflow.backbone.bottleneck import Bottleneck
from geoconv.tensorflow.backbone.covariance import Covariance
from geoconv.tensorflow.layers.point_cloud_normals import PointCloudNormals

import tensorflow as tf


class ModelNetClf(tf.keras.Model):
    def __init__(self,
                 n_radial,
                 n_angular,
                 template_radius,
                 isc_layer_conf,
                 neighbors_for_lrf=16,
                 modelnet10=False,
                 variant=None,
                 rotation_delta=1,
                 initializer="glorot_uniform",
                 pooling="cov",
                 noise_stddev=1e-3):
        super().__init__()

        #############
        # INPUT PART
        #############
        # For centering point clouds
        self.normals = PointCloudNormals(neighbors_for_lrf=16)

        #################
        # EMBEDDING PART
        #################
        # Determine which layer type shall be used
        assert variant in ["dirac", "geodesic"], "Please choose a layer type from: ['dirac', 'geodesic']."

        # Define embedding architecture
        self.isc_layers = []
        for (dims, vertices) in isc_layer_conf:
            self.isc_layers.append(
                Bottleneck(
                    amount_vertices=vertices,
                    intermediate_dims=dims[:-1],
                    pre_bottleneck_dim=dims[-1],
                    n_radial=n_radial,
                    n_angular=n_angular,
                    neighbors_for_lrf=neighbors_for_lrf,
                    template_radius=template_radius,
                    noise_stddev=noise_stddev,
                    rotation_delta=rotation_delta,
                    variant=variant,
                    initializer=initializer
                )
            )

        ######################
        # CLASSIFICATION PART
        ######################
        assert pooling in ["cov", "max", "avg"], "Please set your pooling to either 'cov', 'max' or 'avg'."
        if pooling == "cov":
            self.pool = Covariance()
        elif pooling == "avg":
            self.pool = tf.keras.layers.GlobalAvgPool1D(data_format="channels_last")
        else:
            self.pool = tf.keras.layers.GlobalMaxPool1D(data_format="channels_last")

        # Define classification layer
        self.output_dim = 10 if modelnet10 else 40
        self.clf = tf.keras.layers.Dense(units=self.output_dim, activation="linear")

    def call(self, inputs, training=False, **kwargs):
        # Compute covariance of normals
        coordinates = inputs
        signal = self.normals(coordinates)

        # Compute vertex embeddings
        for idx in tf.range(len(self.isc_layers)):
            coordinates, signal = self.isc_layers[idx]([coordinates, signal])

        # Pool local surface descriptors into global point-cloud descriptor
        signal = self.pool(signal)

        # Return classification of point-cloud descriptor
        return self.clf(signal)
