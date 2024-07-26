from geoconv.utils.data_generator import preprocessed_shape_generator

from io import BytesIO

import numpy as np
import trimesh
import tensorflow as tf


MODELNET_CLASSES = {
    "airplane": 0,
    "bathtub": 1,
    "bed": 2,
    "bench": 3,
    "bookshelf": 4,
    "bottle": 5,
    "bowl": 6,
    "car": 7,
    "chair": 8,
    "cone": 9,
    "cup": 10,
    "curtain": 11,
    "desk": 12,
    "door": 13,
    "dresser": 14,
    "flower_pot": 15,
    "glass_box": 16,
    "guitar": 17,
    "keyboard": 18,
    "lamp": 19,
    "laptop": 20,
    "mantel": 21,
    "monitor": 22,
    "night_stand": 23,
    "person": 24,
    "piano": 25,
    "plant": 26,
    "radio": 27,
    "range_hood": 28,
    "sink": 29,
    "sofa": 39,
    "stairs": 31,
    "stool": 32,
    "table": 33,
    "tent": 34,
    "toilet": 35,
    "tv_stand": 36,
    "vase": 37,
    "wardrobe": 38,
    "xbox": 39
}

# MODELNET10_CLASSES = {
#     "bathtub": 0,
#     "bed": 1,
#     "chair": 2,
#     "desk": 3,
#     "dresser": 4,
#     "monitor": 5,
#     "night_stand": 6,
#     "sofa": 7,
#     "table": 8,
#     "toilet": 9
# }
MODELNET10_CLASSES = {"cup": 0, "bowl": 1}


def modelnet_generator(dataset_path,
                       n_radial,
                       n_angular,
                       template_radius,
                       is_train,
                       only_signal=False,
                       batch=1,
                       modelnet10=False,
                       gen_info_file=""):
    prefix = "train" if is_train else "test"
    if modelnet10:
        classes = list(MODELNET10_CLASSES.keys())
        filter_list = [f"{prefix}/{c}_.*stl" for c in classes]
        filter_list += [f"{prefix}/{c}_.*BC_{n_radial}_{n_angular}_{template_radius}" for c in classes]
    else:
        filter_list = [f"{prefix}.*stl", f"{prefix}.*BC_{n_radial}_{n_angular}_{template_radius}"]

    # Load preprocessed shapes
    psg = preprocessed_shape_generator(
        dataset_path, filter_list=filter_list, batch=batch, shuffle_seed=42, zero_pad=2086, gen_info_file=gen_info_file
    )

    for ((stl, stl_path), (bc, bc_path)) in psg:
        if is_train:
            noise = np.abs(np.random.normal(size=(bc.shape[0], n_radial, n_angular, 3, 2), scale=1e-5))
            noise[:, :, :, :, 0] = 0
            bc = bc + noise

        vertices = trimesh.load_mesh(BytesIO(stl), file_type="stl").vertices
        # Zero pad signal
        while vertices.shape[0] < bc.shape[0]:
            vertices = np.concatenate([vertices, np.zeros_like(vertices)[:bc.shape[0] - vertices.shape[0]]])

        if only_signal:
            yield vertices
        else:
            if modelnet10:
                yield (vertices, bc), np.array(MODELNET10_CLASSES[stl_path.split("/")[1]]).reshape(1)
            else:
                yield (vertices, bc), np.array(MODELNET_CLASSES[stl_path.split("/")[1]]).reshape(1)


def load_preprocessed_modelnet(path_to_zip,
                               n_radial,
                               n_angular,
                               template_radius,
                               is_train,
                               only_signal=False,
                               batch=1,
                               modelnet10=False,
                               gen_info_file=""):
    if only_signal:
        output_signature = tf.TensorSpec(shape=(None, 3), dtype=tf.float32)
    else:
        output_signature = (
            (
                tf.TensorSpec(shape=(None, 3), dtype=tf.float32),  # Signal  (3D coordinates)
                tf.TensorSpec(shape=(None,) + (n_radial, n_angular) + (3, 2), dtype=tf.float32)  # Barycentric Coordinates
            ),
            tf.TensorSpec(shape=(None,), dtype=tf.float32)
        )

    return tf.data.Dataset.from_generator(
        modelnet_generator,
        args=(
            path_to_zip,
            n_radial,
            n_angular,
            np.array(template_radius, np.float64),
            is_train,
            only_signal,
            batch,
            modelnet10,
            gen_info_file
        ),
        output_signature=output_signature
    ).batch(batch).prefetch(tf.data.AUTOTUNE)