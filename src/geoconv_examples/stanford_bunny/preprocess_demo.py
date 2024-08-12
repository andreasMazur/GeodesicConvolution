from geoconv.preprocessing.gpc_system_group import GPCSystemGroup
from geoconv.utils.visualization import draw_gpc_triangles, draw_gpc_on_mesh, draw_barycentric_coordinates
from geoconv.utils.misc import reconstruct_template, find_largest_one_hop_dist, normalize_mesh, compute_distance_matrix
from geoconv.preprocessing.barycentric_coordinates import compute_barycentric_coordinates, create_template_matrix

import open3d as o3d
import trimesh
import os
import numpy as np


def load_bunny(path, target_triangles_amount=6000):
    """Loads and simplifies the Stanford bunny

    Download the Stanford bunny from here:
    https://github.com/alecjacobson/common-3d-test-models/blob/master/data/stanford-bunny.zip

    Unzip the .zip-file and move the 'bun_zipper.ply'-file into the folder where this demo-file
    is saved.

    Parameters
    ----------
    target_triangles_amount: int
        The amount of target triangles of the stanford bunny triangle mesh. Watch out, the target
        amount of triangles is not guaranteed!
    path: str
        If the path to the Stanford bunny .ply-file differs from 'PATH_TO_STANFORD_BUNNY' you can
        set it correctly with the 'path'-argument.

    Returns
    -------
    trimesh.Trimesh:
        The Stanford bunny triangle mesh.
    """

    b = o3d.io.read_triangle_mesh(path)
    b = b.simplify_quadric_decimation(target_number_of_triangles=target_triangles_amount)
    b = trimesh.Trimesh(vertices=b.vertices, faces=b.triangles)

    return b


def preprocess_demo(path_to_stanford_bunny="bun_zipper.ply",
                    n_radial=3,
                    n_angular=8,
                    processes=1,
                    k_th_neighbor=20):
    """Demonstrates and visualizes GeoConv's preprocessing at the hand of the stanford bunny.

    Download the Stanford bunny from here:
    https://github.com/alecjacobson/common-3d-test-models/blob/master/data/stanford-bunny.zip

    Unzip the .zip-file and move the 'bun_zipper.ply'-file and enter the path to the 'bun_zipper.ply' as argument
    for 'path_to_stanford_bunny'.

    Parameters
    ----------
    path_to_stanford_bunny: str
        The path to the 'bun_zipper.ply'-file containing the stanford bunny.
    n_radial: int
        The amount of radial coordinates for the template in your geodesic convolution.
    n_angular: int
        The amount of angular coordinates for the template in your geodesic convolution.
    processes: int
        The amount of concurrent processes that shall compute the GPC-systems.
    k_th_neighbor: int
        The k-th nearest neighbor for calculating the local GPC-system radius.
    """
    target_dir = "./preprocess_demo_plots"
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    # Load the stanford bunny in '.ply'-format as a trimesh-object.
    bunny = load_bunny(path_to_stanford_bunny)

    # Find the smallest distance from a center vertex in the bunny mesh to one of its one-hop neighbors.
    bunny, _ = normalize_mesh(bunny, geodesic_diameter=0.25270776231631265)

    # Use distance of k-th nearest neighbor for maximum GPC-system radius
    distance_matrix = compute_distance_matrix(bunny.vertices)
    distance_matrix.sort(axis=-1)
    u_max = distance_matrix[:, k_th_neighbor]

    # Compute and store the GPC-systems for the bunny mesh.
    gpc_systems_path = f"{os.path.dirname(path_to_stanford_bunny)}/bunny_gpc_systems"
    if not os.path.exists(gpc_systems_path):
        gpc_systems = GPCSystemGroup(bunny, processes=processes)
        gpc_systems.compute(u_max=u_max)
        gpc_systems.save(gpc_systems_path)
    else:
        gpc_systems = GPCSystemGroup(bunny, processes=processes)
        gpc_systems.load(gpc_systems_path)

    # Select the template radius to be the average GPC-system radius
    template_radius = u_max.mean()

    # Compute the barycentric coordinates for the template in the computed GPC-systems.
    bc = compute_barycentric_coordinates(
        gpc_systems, n_radial=n_radial, n_angular=n_angular, radius=template_radius
    )
    np.save(f"{os.path.dirname(path_to_stanford_bunny)}/bunny_barycentric_coordinates.npy", bc)

    ####################################################################
    # Visualization of the GPC-systems and the barycentric coordinates
    ####################################################################
    for gpc_system_idx in range(3):  # select which GPC-systems you want to visualize by altering the list

        # Original template
        template_matrix = create_template_matrix(
            n_radial=n_radial, n_angular=n_angular, radius=template_radius, in_cart=True
        )
        # Create template with barycentric coordinates
        reconstructed_template = reconstruct_template(
            gpc_systems.object_mesh_gpc_systems[gpc_system_idx].get_gpc_system(), bc[gpc_system_idx]
        )

        for radial_coordinate in range(bc.shape[1]):
            for angular_coordinate in range(bc.shape[2]):
                print(
                    f"Location: {(gpc_system_idx, radial_coordinate, angular_coordinate)}: "
                    f"Vertices: {bc[gpc_system_idx, radial_coordinate, angular_coordinate, :, 0]} "
                    f"B.c: {bc[gpc_system_idx, radial_coordinate, angular_coordinate, :, 1]} "
                    f"-> Caused: {reconstructed_template[radial_coordinate, angular_coordinate]}"
                )
        print("==========================================================================")

        # Draw GPC-system on the mesh (center_vertex, radial_coordinates, angular_coordinates, object_mesh)
        draw_gpc_on_mesh(
            gpc_system_idx,
            gpc_systems.object_mesh_gpc_systems[gpc_system_idx].radial_coordinates,
            gpc_systems.object_mesh_gpc_systems[gpc_system_idx].angular_coordinates,
            bunny
        )

        # Original/Set template vertices
        draw_gpc_triangles(
            gpc_systems.object_mesh_gpc_systems[gpc_system_idx],
            template_matrix=template_matrix,
            plot=True,
            title="GPC-system",
            save_name=f"{target_dir}/gpc_system_{gpc_system_idx}"
        )

        # Draw triangles with stored GPC-coordinates and place reconstructed template vertices with the help of the
        # computed barycentric coordinates
        draw_barycentric_coordinates(
            gpc_systems.object_mesh_gpc_systems[gpc_system_idx],
            bc[gpc_system_idx],
            save_name=f"{target_dir}/gpc_system_{gpc_system_idx}"
        )
