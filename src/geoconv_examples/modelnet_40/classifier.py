from geoconv.tensorflow.backbone.covariance import Covariance
from geoconv.tensorflow.backbone.resnet_block import ResNetBlock
from geoconv.tensorflow.layers.barycentric_coordinates import BarycentricCoordinates
from geoconv.tensorflow.layers.normalize_point_cloud import NormalizePointCloud
from geoconv.tensorflow.layers.pooling.gravity_pooling import GravityPooling
from geoconv.tensorflow.layers.shot_descriptor import PointCloudShotDescriptor
from geoconv.tensorflow.layers.spatial_dropout import SpatialDropout

import tensorflow as tf


class WarmupAndExpDecay(tf.keras.optimizers.schedules.LearningRateSchedule):
    def __init__(self, initial_learning_rate, decay_rate, decay_steps, warmup_steps):
        self.initial_learning_rate = initial_learning_rate
        self.decay_rate = decay_rate
        self.warmup_steps = warmup_steps
        self.decay_steps = decay_steps

    def __call__(self, step):
        if step >= self.warmup_steps:
            return self.initial_learning_rate * self.decay_rate ** ((step - self.warmup_steps) / self.decay_steps)
        else:
            return step / self.warmup_steps * self.initial_learning_rate

    def get_config(self):
        return {
            "initial_learning_rate": self.initial_learning_rate,
            "decay_rate": self.decay_rate,
            "decay_steps": self.decay_steps,
            "warmup_steps": self.warmup_steps
        }


class ModelNetClf(tf.keras.Model):
    def __init__(self,
                 n_radial,
                 n_angular,
                 template_radius,
                 isc_layer_conf,
                 down_sample_pc,
                 neighbors_for_lrf=32,
                 projection_neighbors=10,
                 modelnet10=False,
                 variant=None,
                 rotation_delta=1,
                 pooling="avg",
                 azimuth_bins=8,
                 elevation_bins=2,
                 radial_bins=2,
                 histogram_bins=11,
                 sphere_radius=0.,
                 dropout_rate=0.,
                 exp_lambda=2.0,
                 shift_angular=True,
                 time=1.,
                 iterations=3):
        super().__init__()

        #############
        # INPUT PART
        #############
        # For centering point clouds
        self.normalize_point_cloud = NormalizePointCloud()

        # For initial vertex signals
        self.shot_descriptor = PointCloudShotDescriptor(
            neighbors_for_lrf=neighbors_for_lrf,
            azimuth_bins=azimuth_bins,
            elevation_bins=elevation_bins,
            radial_bins=radial_bins,
            histogram_bins=histogram_bins,
            sphere_radius=sphere_radius,
        )

        # Init barycentric coordinates layer
        self.bc_layer = BarycentricCoordinates(
            n_radial=n_radial,
            n_angular=n_angular,
            neighbors_for_lrf=neighbors_for_lrf,
            projection_neighbors=projection_neighbors
        )
        self.bc_layer.adapt(template_radius=template_radius, exp_lambda=exp_lambda, shift_angular=shift_angular)

        # Spatial dropout of entire feature maps
        self.dropout = SpatialDropout(rate=dropout_rate)

        # Pooling
        self.pooling = GravityPooling(delta=1.)
        self.time = time
        self.iterations = iterations

        #################
        # EMBEDDING PART
        #################
        # Determine which layer type shall be used
        assert variant in ["dirac", "geodesic"], "Please choose a layer type from: ['dirac', 'geodesic']."

        # Define embedding architecture
        self.down_sample_pc = down_sample_pc
        self.isc_layers = []
        for idx, _ in enumerate(isc_layer_conf):
            self.isc_layers.append(
                ResNetBlock(
                    amt_templates=isc_layer_conf[idx],
                    template_radius=template_radius + idx * 0.25 * template_radius,
                    rotation_delta=rotation_delta,
                    conv_type=variant,
                    activation="relu",
                    input_dim=-1 if idx == 0 else isc_layer_conf[idx - 1]
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

    def call(self, inputs, **kwargs):
        # Normalize point-cloud
        coordinates = inputs
        coordinates = self.normalize_point_cloud(coordinates)

        # Compute SHOT-descriptor as initial local vertex features
        signal = self.shot_descriptor(coordinates)

        # Compute vertex embeddings
        for idx, _ in enumerate(self.isc_layers):
            # Compute barycentric coordinates from 3D coordinates
            bc = self.bc_layer(coordinates)

            signal = self.dropout(signal)
            signal = self.isc_layers[idx]([signal, bc])

            coordinates, signal = self.pooling(
                [coordinates, signal, self.time, self.iterations, self.down_sample_pc[idx]]
            )

        # Pool local surface descriptors into global point-cloud descriptor
        signal = self.pool(signal)

        # Return classification of point-cloud descriptor
        return self.clf(signal)
