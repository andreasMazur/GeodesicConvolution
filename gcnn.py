from tensorflow.keras.layers import Layer, Activation

import tensorflow as tf


@tf.function
def angular_max_pooling(signal):
    """Angular maximum pooling to filter for the maximal response of a geodesic convolution.

    The signals are measured at the hand of their norms.

    **Input**

    - The result of a geodesic convolution for each rotation in a tensor of size `(m, r, o)`, where `m` is the amount
      of nodes on the mesh, `r` the amount of rotations and `o` the output dimension of the convolution.

    **Output**

    - A tensor containing the maximal response at each vertex. Compare Eq. (12) in [1].

    [1]:
    > Jonathan Masci, Davide Boscaini, Michael M. Bronstein, Pierre Vandergheynst

    > [Geodesic Convolutional Neural Networks on Riemannian Manifolds](https://www.cv-foundation.org/
    openaccess/content_iccv_2015_workshops/w22/html/Masci_Geodesic_Convolutional_Neural_ICCV_2015_paper.html)

    """
    row_indices = tf.argmax(tf.norm(signal, ord="euclidean", axis=-1), axis=0)
    column_indices = tf.range(tf.shape(signal)[1], dtype=tf.int64)
    indices = tf.stack([row_indices, column_indices], axis=1)
    return tf.gather_nd(signal, indices)


@tf.function
def signal_pullback(signal, bary_coords):
    """Computes the pullback of signals onto the position of a kernel vertex.

    **Input**

    - `signal`: A Tensor containing the signal on the graph. It has the size `(m, n)` where `m` is the amount of
      nodes in the graph and `n` the dimensionality of the signal on the graph.

    - `barycentric_coords_vertex`: The barycentric coordinates for all kernel vertices of one local GPC-system. The form
      should be of the one described in `barycentric_coords_local_gpc`.

    **Output**

    - A tensor representing the pullback of the signal onto the position of the kernel vertex. The dimensionality of the
      tensor corresponds to the dimensionality of the input signal.

    """
    vertex_signals = tf.gather(signal, tf.cast(tf.reshape(bary_coords[:, :, 1], (-1,)), tf.int32))
    fst_weighted_sig = tf.reshape(bary_coords[:, :, 0], (-1, 1)) * vertex_signals

    vertex_signals = tf.gather(signal, tf.cast(tf.reshape(bary_coords[:, :, 3], (-1,)), tf.int32))
    snd_weighted_sig = tf.reshape(bary_coords[:, :, 2], (-1, 1)) * vertex_signals

    vertex_signals = tf.gather(signal, tf.cast(tf.reshape(bary_coords[:, :, 5], (-1,)), tf.int32))
    thr_weighted_sig = tf.reshape(bary_coords[:, :, 4], (-1, 1)) * vertex_signals

    result = tf.reduce_sum([fst_weighted_sig, snd_weighted_sig, thr_weighted_sig], axis=0)
    return tf.reshape(result, (tf.shape(bary_coords)[0], tf.shape(bary_coords)[1], -1))


class ConvGeodesic(Layer):

    def __init__(self, kernel_size, output_dim, amt_kernel, activation="relu"):
        super().__init__()

        # Define kernel attributes
        self.kernel = None
        self.kernel_size = kernel_size  # (#radial, #angular)

        # Define output attributes
        self.output_dim = output_dim  # dimension of the output signal
        self.activation = Activation(activation)

        # Define convolution attributes
        self.all_rotations = self.kernel_size[1]
        self.amt_kernel = amt_kernel

    def get_config(self):
        config = super(ConvGeodesic, self).get_config()
        config.update(
            {
                "kernel_size": self.kernel_size,
                "output_dim": self.output_dim,
                "activation": self.activation,
                "all_rotations": self.all_rotations,
                "amt_kernel": self.amt_kernel
            }
        )
        return config

    def build(self, input_shape):
        """Defines the kernel for the geodesic convolution layer.

        In one layer we have:
            * `self.amt_kernel`-many kernels (referred to as 'filters' in [1]).
            * With `(self.kernel_size[0], self.kernel_size[1])` we reference to a weight matrix corresponding to a
              kernel vertex.
            * With `(self.output_dim, input_shape[1])` we define the size of the weight matrix of a kernel vertex.
              With `self.output_dim` we modify the output dimensionality of the signal after the convolution.

        An expressive illustration of how these kernels are used during the convolution is given in Figure 3 in [1].

        [1]:
        > Jonathan Masci, Davide Boscaini, Michael M. Bronstein, Pierre Vandergheynst

        > [Geodesic Convolutional Neural Networks on Riemannian Manifolds](https://www.cv-foundation.org/
        openaccess/content_iccv_2015_workshops/w22/html/Masci_Geodesic_Convolutional_Neural_ICCV_2015_paper.html)


        **Input**

        - `input_shape`: The shape of the tensor containing the signal on the graph.

        """
        signal_shape, _ = input_shape
        self.kernel = self.add_weight(
            "Kernel",
            # Broadcasting in convolution requires to make angular coordinate first coordinate
            shape=(self.amt_kernel, self.kernel_size[1], self.kernel_size[0], self.output_dim, signal_shape[2]),
            initializer="glorot_uniform",
            trainable=True
        )

    @tf.function
    def call(self, inputs):
        """The geodesic convolution Layer performs a geodesic convolution.

        This layer computes the geodesic convolution for all vertices `v`:

            (f (*) K)[v] = max_r{ activation(sum_ij: K[i, (j+r) % N_theta] * x[i, j]) }

            x[i, j] = E[v, i, j, x1] * f[x1] + E[v, i, j, x2] * f[x2] + E[v, i, j, x3] * f[x3]

        With K[i, j] containing the weight-matrix for a kernel vertex and x[i, j] being the interpolated signal at the
        kernel vertex (i, j). Furthermore, x1, x2 and x3 are the nodes in the mesh used to interpolate the signal at
        the kernel vertex (i, j) [usually the triangle including it]. E contains the necessary Barycentric coordinates
        for the interpolation. Compare Equation (7) and (11) in [1] as well as section 4.4 in [2].

        [1]:
        > Jonathan Masci, Davide Boscaini, Michael M. Bronstein, Pierre Vandergheynst

        > [Geodesic Convolutional Neural Networks on Riemannian Manifolds](https://www.cv-foundation.org/
        openaccess/content_iccv_2015_workshops/w22/html/Masci_Geodesic_Convolutional_Neural_ICCV_2015_paper.html)

        [2]:
        > Adrien Poulenard and Maks Ovsjanikov.

        > [Multi-directional geodesic neural networks via equivariant convolution.](https://dl.acm.org/doi/abs/10.1145/
        3272127.3275102)

        **Input**

        - `inputs`:
            * A tensor containing the signal on the graph. It has the size `(m, n)` where `m` is the amount of
              nodes in the graph and `n` the dimensionality of the signal on the graph.
            * A tensor containing the Barycentric coordinates corresponding to the kernel defined for this layer.
              It has the size `(m, self.kernel_size[0] * self.kernel_size[1], 8)` and is structured like described in
              `barycentric_coordinates.barycentric_coords.barycentric_coords_local_gpc`.

        **Output**

        - A tensor of size `(m, o)` representing the geodesic convolution of the signal with the layer's kernel. Here,
          `m` is the amount of nodes in the graph and `o` is the desired output dimension of the signal.

        """

        signal, b_coordinates = inputs
        result_tensor = tf.TensorArray(tf.float32, size=0, dynamic_size=True, clear_after_read=False)
        batch_size = tf.shape(signal)[0]
        for idx in tf.range(batch_size):
            new_signal = self._geodesic_convolution(signal[idx], b_coordinates[idx])
            result_tensor = result_tensor.write(idx, new_signal)
        return result_tensor.stack()

    @tf.function
    def _geodesic_convolution(self, signal, barycentric_coords):
        """Wrapper for computing the geodesic convolution w.r.t. each rotation.

        In essence this function computes for all r in self.all_rotations:
            sum_ij: K[i, (j+r) % N_theta] * x[i, j]

        **Input**

        - `inputs`: A Tensor containing the signal on the graph. It has the size `(m, n)` where `m` is the amount of
          nodes in the graph and `n` the dimensionality of the signal on the graph.

        - `barycentric_coords_gpc`: The barycentric coordinates for each kernel vertex of one local GPC-system. The form
          should be of the one described in `barycentric_coords_local_gpc`.

        **Output**

        - A tensor of size `(p, o)` where `p` is the amount of all considered rotations and `o` is the desired output
          dimensionality of the convolved signal.

        """

        pullback_fn = lambda local_gpc_system: signal_pullback(signal, local_gpc_system)
        pullback = tf.vectorized_map(pullback_fn, barycentric_coords)

        # We will need to sum over the convolutions of every kernel
        kernels = tf.TensorArray(tf.float32, size=0, dynamic_size=True, clear_after_read=False)
        for k in tf.range(self.amt_kernel):
            # We will need to consider every rotation of each kernel
            kernel_rotations = tf.TensorArray(tf.float32, size=0, dynamic_size=True, clear_after_read=False)
            for rotation in tf.range(self.all_rotations):
                angular_convolutions = tf.TensorArray(tf.float32, size=0, dynamic_size=True, clear_after_read=False)
                for angular_coord in tf.range(self.kernel_size[1]):
                    # Compute the product from within the sum of Eq. (7) in [1]
                    rotation = tf.math.floormod(angular_coord + rotation, self.kernel_size[1])
                    angular_convolutions = angular_convolutions.write(
                        rotation,
                        tf.linalg.matvec(self.kernel[k, rotation], pullback[:, angular_coord])
                    )
                angular_convolutions = angular_convolutions.stack()
                kernel_rotations = kernel_rotations.write(rotation, angular_convolutions)
            kernel_rotations = kernel_rotations.stack()
            kernels = kernels.write(k, kernel_rotations)
        kernels = kernels.stack()

        # Compute the sum over all filter banks (0), as well as radial (2) and angular (4) coordinates
        # Compare Equations (7) and (11) in [1]
        kernels = tf.reduce_sum(kernels, axis=[0, 2, 4])
        kernels = self.activation(kernels)
        return angular_max_pooling(kernels)
