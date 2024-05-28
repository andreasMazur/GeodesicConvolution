from geoconv.utils.data_generator import barycentric_coordinates_generator

import tensorflow as tf
import tensorflow_datasets as tfds


def load_preprocessed_mnist(bc_path, n_radial, n_angular, template_radius, set_type):
    """Adds barycentric coordinates to the MNIST dataset and reshapes images to vectors.

    Parameters
    ----------
    bc_path: str
        The path to the preprocessed dataset.
    n_radial: int
        The amount of radial coordinates used during BC-computation.
    n_angular: int
        The amount of angular coordinates used during BC-computation.
    template_radius: float
        The considered template radius during BC-computation.
    set_type: str
        The set type according to the common split-nomenclature in tensorflow-datasets.

    Returns
    -------
    tensorflow.data.Dataset:
        A dataset containing MNIST-images and labels together with barycentric coordinates to train an IMCNN.
    """
    # Load MNIST
    dataset = tfds.load("mnist", split=set_type, shuffle_files=True, as_supervised=True)

    # Load barycentric coordinates
    barycentric_coordinates = barycentric_coordinates_generator(
        bc_path, n_radial, n_angular, template_radius, return_filename=False
    )

    for bc in barycentric_coordinates:
        bc = tf.cast(tf.constant(bc), tf.float32)

        # Reshapes the image to a vector and adds barycentric coordinates
        def make_compatible(image, label):
            image = tf.cast(tf.reshape(image, (-1, 1)), tf.float32)
            label = tf.cast(label, tf.int32)
            return (image, bc), label

        # Apply 'make_compatible' to each element of MNIST
        dataset = dataset.map(make_compatible)
    return dataset.batch(1).prefetch(tf.data.AUTOTUNE)
