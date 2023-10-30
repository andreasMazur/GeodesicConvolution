from geoconv.layers.legacy.conv_intrinsic import ConvIntrinsic
from geoconv.layers.conv_exp import exp_pdf

import numpy as np
import scipy as sp


class ConvExp(ConvIntrinsic):
    """Exponential vertex weighting"""
    def __init__(self, *args, exp_lambda=1, **kwargs):
        super().__init__(*args, **kwargs)
        self.exp_lambda = exp_lambda

    def define_interpolation_coefficients(self, template_matrix):
        template_matrix[:, :, 0] = template_matrix[:, :, 0] / template_matrix[:, :, 0].max()
        interpolation_coefficients = np.zeros(template_matrix.shape[:-1] + template_matrix.shape[:-1])
        for mean_rho_idx in range(template_matrix.shape[0]):
            for mean_theta_idx in range(template_matrix.shape[1]):
                mean_rho, mean_theta = template_matrix[mean_rho_idx, mean_theta_idx]
                for rho_idx in range(template_matrix.shape[0]):
                    for theta_idx in range(template_matrix.shape[1]):
                        rho, theta = template_matrix[rho_idx, theta_idx]
                        interpolation_coefficients[mean_rho_idx, mean_theta_idx, rho_idx, theta_idx] = exp_pdf(
                            mean_rho, mean_theta, rho, theta, self.exp_lambda
                        )
                interpolation_coefficients[mean_rho_idx, mean_theta_idx] = sp.special.softmax(
                    interpolation_coefficients[mean_rho_idx, mean_theta_idx]
                )
        return interpolation_coefficients