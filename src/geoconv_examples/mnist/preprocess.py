from geoconv.preprocessing.barycentric_coordinates import compute_barycentric_coordinates
from geoconv.preprocessing.gpc_system_group import GPCSystemGroup
from geoconv.utils.common import compute_gpc_systems

from matplotlib import pyplot as plt

import numpy as np
import scipy as sp
import trimesh
import shutil
import json


def create_grid(n_vertices):
    # Get mesh faces
    coordinates = np.linspace(start=0, stop=1, num=n_vertices)
    grid_vertices = np.array([(x, y) for x in coordinates for y in coordinates])
    grid_faces = sp.spatial.Delaunay(grid_vertices).simplices

    # Make vertices 3D (but keep it flat)
    grid_vertices = np.concatenate([grid_vertices, np.zeros(n_vertices ** 2).reshape(-1, 1)], axis=-1)

    return trimesh.Trimesh(vertices=grid_vertices, faces=grid_faces)


def image_to_grid(image, grid):
    grid_image = trimesh.PointCloud(grid.vertices, colors=plt.cm.binary(np.array(image).reshape((-1))))
    trimesh.Scene([grid, grid_image]).show()


def compute_bc(preprocess_dir):

    with open(f"{preprocess_dir}/preprocess_properties.json") as properties_file:
        properties = json.load(properties_file)
        gpc_system_radius = properties["gpc_system_radius"]

    # Load GPC-systems
    gpc_systems = GPCSystemGroup(object_mesh=trimesh.load_mesh(f"{preprocess_dir}/normalized_mesh.stl"))
    gpc_systems.load(f"{preprocess_dir}/gpc_systems")

    # Define template configurations
    template_configurations = [
        (3, 6, gpc_system_radius * .75),
        (3, 6, gpc_system_radius),
        (3, 6, gpc_system_radius * 1.25),
        (5, 8, gpc_system_radius * .75),
        (5, 8, gpc_system_radius),
        (5, 8, gpc_system_radius * 1.25)
    ]

    for (n_radial, n_angular, template_radius) in template_configurations:
        bc = compute_barycentric_coordinates(
            gpc_systems, n_radial=n_radial, n_angular=n_angular, radius=template_radius
        )
        np.save(f"{preprocess_dir}/BC_{n_radial}_{n_angular}_{template_radius}.npy", bc)

    print(f"Barycentric coordinates done. Zipping..")
    shutil.make_archive(base_name=preprocess_dir, format="zip", root_dir=preprocess_dir)
    shutil.rmtree(preprocess_dir)
    print("Done.")


def preprocess(output_path, processes):
    # Preprocess flat grid
    grid = create_grid(n_vertices=28)  # MNIST-images are 28x28
    compute_gpc_systems(grid, output_path, processes=processes)
    compute_bc(output_path)
