import numpy as np
import trimesh
import os


def raw_data_generator(path, return_file_name=False, file_boundaries=None):
    """Loads the manually labeled data."""
    directory = os.listdir(f"{path}/out_data")
    directory.sort()
    if file_boundaries is not None:
        directory = directory[file_boundaries[0]:file_boundaries[1]]
    for file_name in directory:
        d = np.load(f'{path}/out_data/{file_name}')
        if return_file_name:
            yield trimesh.Trimesh(vertices=d["verts"], faces=d["faces"], validate=True), d["labels"], file_name
        else:
            yield trimesh.Trimesh(vertices=d["verts"], faces=d["faces"], validate=True), d["labels"]
