from geoconv.utils.data_generator import preprocessed_shape_generator

import tensorflow as tf
import numpy as np
import random


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
    "sofa": 30,
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
MN_CLASS_WEIGHTS ={
    "airplane": 0.039968038348871575,
    "bathtub": 0.09712858623572641,
    "bed": 0.044065264923923174,
    "bench": 0.07602859212697055,
    "bookshelf": 0.04181210050035454,
    "bottle": 0.05463583647081531,
    "bowl": 0.125,
    "car": 0.07124704998790965,
    "chair": 0.033538923545276884,
    "cone": 0.07738232325341368,
    "cup": 0.1125087900926024,
    "curtain": 0.08512565307587486,
    "desk": 0.07071067811865475,
    "door": 0.09578262852211514,
    "dresser": 0.07071067811865475,
    "flower_pot": 0.08192319205190406,
    "glass_box": 0.07647191129018725,
    "guitar": 0.08032193289024989,
    "keyboard": 0.08304547985373997,
    "lamp": 0.08980265101338746,
    "laptop": 0.08192319205190406,
    "mantel": 0.05933908290969266,
    "monitor": 0.04637388957601683,
    "night_stand": 0.07071067811865475,
    "person": 0.10660035817780521,
    "piano": 0.0657951694959769,
    "plant": 0.06454972243679027,
    "radio": 0.09805806756909202,
    "range_hood": 0.09325048082403138,
    "sink": 0.08838834764831843,
    "sofa": 0.03834824944236852,
    "stairs": 0.08980265101338746,
    "stool": 0.10540925533894598,
    "table": 0.050507627227610534,
    "tent": 0.07832604499879574,
    "toilet": 0.053916386601719206,
    "tv_stand": 0.06119900613621046,
    "vase": 0.04588314677411235,
    "wardrobe": 0.10721125348377948,
    "xbox": 0.09853292781642932
}

MODELNET10_CLASSES = {
    "bathtub": 0,
    "bed": 1,
    "chair": 2,
    "desk": 3,
    "dresser": 4,
    "monitor": 5,
    "night_stand": 6,
    "sofa": 7,
    "table": 8,
    "toilet": 9
}
MN10_CLASS_WEIGHTS = {
    "bathtub": 0.09712858623572641,
    "bed": 0.044065264923923174,
    "chair": 0.033538923545276884,
    "desk": 0.07071067811865475,
    "dresser": 0.07071067811865475,
    "monitor": 0.04637388957601683,
    "night_stand": 0.07071067811865475,
    "sofa": 0.03834824944236852,
    "table": 0.050507627227610534,
    "toilet": 0.053916386601719206
}

DEBUG_DATASET_SIZE = 100


def shuffle_directive(shape_dict):
    shape_dict_keys = list(shape_dict.keys())
    random.shuffle(shape_dict_keys)
    return {key: shape_dict[key] for key in shape_dict_keys}


def modelnet_generator(dataset_path,
                       set_type,
                       modelnet10=False,
                       gen_info_file="",
                       debug_data=False,
                       in_one_hot=False):
    if isinstance(set_type, bytes):
        set_type = set_type.decode("utf-8")

    if set_type not in ["train", "test", "all"]:
        raise RuntimeError(f"Unknown dataset type: '{set_type}' Please select from: ['train', 'test', 'all'].")

    set_type = "" if set_type == "all" else set_type
    if modelnet10:
        filter_list = list(MODELNET10_CLASSES.keys())
        filter_list = [f"{set_type}/{c}_.*/vertices" for c in filter_list]
    else:
        filter_list = [f"{set_type}.*vertices"]

    # Load sampled vertices from preprocessed dataset
    psg = preprocessed_shape_generator(
        zipfile_path=dataset_path,
        filter_list=filter_list,
        batch_size=1,
        generator_info=gen_info_file,
        directive=shuffle_directive
    )

    for idx, shape in enumerate(psg):
        point_cloud, file_path = shape[0]

        # Check whether this dataset is intended for debugging
        if idx == DEBUG_DATASET_SIZE and debug_data:
            break

        # Check whether to use ModelNet10 labels
        if modelnet10:
            n_classes = 10
            label = np.array(MODELNET10_CLASSES[file_path.split("/")[1]]).reshape(1)
        else:
            n_classes = 40
            label = np.array(MODELNET_CLASSES[file_path.split("/")[1]]).reshape(1)

        # Check whether labels are supposed to be one-hot encoded
        if in_one_hot:
            label = np.eye(n_classes)[label[0]]

        yield point_cloud, label


def load_preprocessed_modelnet(dataset_path,
                               set_type,
                               batch_size=4,
                               modelnet10=False,
                               gen_info_file="",
                               debug_data=False,
                               in_one_hot=False):
    n_classes = 10 if modelnet10 else 40
    if in_one_hot:
        output_signature = (
            tf.TensorSpec(shape=(None, 3), dtype=tf.float32),
            tf.TensorSpec(shape=(n_classes,), dtype=tf.float32)
        )
    else:
        output_signature = (
            tf.TensorSpec(shape=(None, 3), dtype=tf.float32),
            tf.TensorSpec(shape=(1,), dtype=tf.float32)
        )

    return tf.data.Dataset.from_generator(
        modelnet_generator,
        args=(dataset_path, set_type, modelnet10, gen_info_file, debug_data, in_one_hot),
        output_signature=output_signature
    ).batch(batch_size).prefetch(tf.data.AUTOTUNE)
