# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# (C) British Crown Copyright 2017 Met Office.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""
This module defines the utilities required for Ensemble Copula Coupling
plugins.

"""
import copy
import numpy as np
import random

import cf_units as unit
import iris
from iris.exceptions import CoordinateNotFoundError

from improver.ensemble_copula_coupling.ensemble_copula_coupling_constants \
    import bounds_for_ecdf


def concatenate_2d_array_with_2d_array_endpoints(
        array_2d, low_endpoint, high_endpoint):
    """
    For a 2d array, add a 2d array as the lower and upper endpoints.
    The concatenation to add the lower and upper endpoints to the 2d array
    are performed along the second (index 1) dimension.

    Parameters
    ----------
    array_2d : Numpy array
        2d array of values
    low_endpoint : Number
        Number of used to create a 2d array of a constant value
        as the lower endpoint.
    high_endpoint : Number
        Number of used to create a 2d array of a constant value
        as the upper endpoint.
    Returns
    -------
    array_2d : Numpy array
        2d array of values after padding with the low_endpoint and
        high_endpoint.
    """
    lower_array = (
        np.full((array_2d.shape[0], 1), low_endpoint, dtype=array_2d.dtype))
    upper_array = (
        np.full((array_2d.shape[0], 1), high_endpoint, dtype=array_2d.dtype))
    array_2d = np.concatenate(
        (lower_array, array_2d, upper_array), axis=1)
    return array_2d


def choose_set_of_percentiles(no_of_percentiles, sampling="quantile"):
    """
    Function to create percentiles.

    Parameters
    ----------
    no_of_percentiles : Int
        Number of percentiles.
    sampling : String
        Type of sampling of the distribution to produce a set of
        percentiles e.g. quantile or random.
        Accepted options for sampling are:
        Quantile: A regular set of equally-spaced percentiles aimed
                  at dividing a Cumulative Distribution Function into
                  blocks of equal probability.
        Random: A random set of ordered percentiles.

    For further details, Flowerdew, J., 2014.
    Calibrating ensemble reliability whilst preserving spatial structure.
    Tellus, Series A: Dynamic Meteorology and Oceanography, 66(1), pp.1-20.
    Schefzik, R., Thorarinsdottir, T.L. & Gneiting, T., 2013.
    Uncertainty Quantification in Complex Simulation Models Using Ensemble
    Copula Coupling.
    Statistical Science, 28(4), pp.616-640.

    Returns
    -------
    percentiles : List
        Percentiles calculated using the sampling technique specified.

    """
    if sampling in ["quantile"]:
        # Generate percentiles from 1/N+1 to N/N+1.
        percentiles = np.linspace(
            1/float(1+no_of_percentiles),
            no_of_percentiles/float(1+no_of_percentiles),
            no_of_percentiles).tolist()
    elif sampling in ["random"]:
        # Generate percentiles from 1/N+1 to N/N+1.
        # Random sampling doesn't currently sample the ends of the
        # distribution i.e. 0 to 1/N+1 and N/N+1 to 1.
        percentiles = []
        for _ in range(no_of_percentiles):
            percentiles.append(
                random.uniform(
                    1/float(1+no_of_percentiles),
                    no_of_percentiles/float(1+no_of_percentiles)))
        percentiles = sorted(percentiles)
    else:
        msg = "The {} sampling option is not yet implemented.".format(
            sampling)
        raise ValueError(msg)
    return [item*100 for item in percentiles]


def create_cube_with_percentiles(percentiles, template_cube, cube_data,
                                 custom_name=None, cube_unit=None):
    """
    Create a cube with a percentile coordinate based on a template cube.
    The resulting cube will have an extra percentile coordinate compared with
    the template cube. The shape of the cube_data should be the shape of the
    desired output cube.

    Parameters
    ----------
    percentiles : List
        Ensemble percentiles. There should be the same number of percentiles
        as the first dimension of cube_data.
    template_cube : Iris cube
        Cube to copy all coordinates from.
        The template_cube does not contain any existing percentile coordinate.
        Metadata is also copied from this cube.
    cube_data : Numpy array
        Data to insert into the template cube.
        The shape of the cube_data, excluding the dimension associated with
        the percentile coordinate, should be the same as the shape of
        template_cube.
        For example, template_cube shape is (3, 3, 3), whilst the cube_data
        is (10, 3, 3, 3), where there are 10 percentiles.

    Returns
    -------
    result : Iris.cube.Cube
        Cube containing a percentile coordinate as the zeroth dimension
        coordinate in addition to the coordinates and metadata from the
        template cube.

    """
    percentile_coord_name = custom_name or 'percentile_over_realization'

    percentile_coord = iris.coords.DimCoord(
        np.float32(percentiles), long_name=percentile_coord_name,
        units=unit.Unit("%"), var_name=percentile_coord_name)

    metadata_dict = copy.deepcopy(template_cube.metadata._asdict())
    result = iris.cube.Cube(cube_data, **metadata_dict)
    if cube_unit is not None:
        result.units = cube_unit
    result.add_dim_coord(percentile_coord, 0)

    # For the dimension coordinates, the dimensions are incremented by one,
    # as the percentile coordinate has been added as the zeroth coordinate.
    # The dimension associated with the auxiliary and derived coordinates
    # has also been incremented by one.
    for coord in template_cube.dim_coords:
        dim, = template_cube.coord_dims(coord)
        result.add_dim_coord(coord.copy(), dim+1)
    for coord in template_cube.aux_coords:
        dims = template_cube.coord_dims(coord)
        dims = tuple([dim+1 for dim in dims])
        result.add_aux_coord(coord.copy(), dims)
    for coord in template_cube.derived_coords:
        dims = template_cube.coord_dims(coord)
        dims = tuple([dim+1 for dim in dims])
        result.add_aux_coord(coord.copy(), dims)
    return result


def get_bounds_of_distribution(bounds_pairing_key, desired_units):
    """
    Gets the bounds of the distribution and converts the units of the
    bounds_pairing to the desired_units.

    This method gets the bounds values and units from the imported
    dictionaries: bounds_for_ecdf and units_of_bounds_for_ecdf.
    The units of the bounds are converted to be the desired units.

    Parameters
    ----------
    bounds_pairing_key : String
        Name of key to be used for the bounds_for_ecdf dictionary, in order
        to get the desired bounds_pairing.
    desired_units : cf_units.Unit
        Units to which the bounds_pairing will be converted.

    Returns
    -------
    bounds_pairing : Tuple
        Lower and upper bound to be used as the ends of the
        empirical cumulative distribution function, converted to have
        the desired units.

    """
    # Extract bounds from dictionary of constants.
    try:
        bounds_pairing = bounds_for_ecdf[bounds_pairing_key].value
        bounds_pairing_units = bounds_for_ecdf[bounds_pairing_key].units
    except KeyError as err:
        msg = ("The bounds_pairing_key: {} is not recognised "
               "within bounds_for_ecdf {}. \n"
               "Error: {}".format(
                   bounds_pairing_key, bounds_for_ecdf, err))
        raise KeyError(msg)
    bounds_pairing_units = unit.Unit(bounds_pairing_units)
    bounds_pairing = bounds_pairing_units.convert(
        np.array(bounds_pairing), desired_units)
    return bounds_pairing


def insert_lower_and_upper_endpoint_to_1d_array(
        array_1d, low_endpoint, high_endpoint):
    """
    For a 1d array, add a lower and upper endpoint.

    Parameters
    ----------
    array_1d : Numpy array
        1d array of values
    low_endpoint : Number
        Number of use as the lower endpoint.
    high_endpoint : Number
        Number of use as the upper endpoint.
    Returns
    -------
    array_1d : Numpy array
        1d array of values padded with the low_endpoint and high_endpoint.
    """
    lower_array = np.array([low_endpoint])
    upper_array = np.array([high_endpoint])
    array_1d = np.concatenate((lower_array, array_1d, upper_array))
    return array_1d


def restore_non_probabilistic_dimensions(
        array_to_reshape, original_cube, input_probabilistic_dimension_name,
        output_probabilistic_dimension_length):
    """
    Reshape a 2d array, so that it has the dimensions of the original cube,
    whilst ensuring that the probabilistic dimension is the first dimension.

    Parameters
    ----------
    array_to_reshape : Numpy array
        The array that requires reshaping.
    original_cube : Iris.cube.Cube
        Cube containing the desired shape to be reshaped to, apart from the
        probabilistic dimension, for example,
        [probabilistic_dimension, time, y, x].
    input_probabilistic_dimension_name : String
        Name of the dimension within the original cube, which represents the
        probabilistic dimension.
    output_probabilistic_dimension_length : Integer
        Length of the probabilistic dimension, which will be used to create
        the shape to which the array_to_reshape will be reshaped to.
    Returns
    -------
    Numpy array
        The array after reshaping.

    """
    shape_to_reshape_to = list(original_cube.shape)
    if original_cube.coords(
            input_probabilistic_dimension_name, dim_coords=True):
        if original_cube.coord_dims(
                input_probabilistic_dimension_name)[0] == 0:
            pat_coord_position = (
                original_cube.coord_dims(input_probabilistic_dimension_name))
            shape_to_reshape_to.pop(pat_coord_position[0])
        else:
            msg = ("The {} coordinate is a dimension coordinate but is not "
                   "the first dimension coordinate in the cube: {}.\n"
                   "The ensure_dimension_is_the_first_dimension function "
                   "may be useful. ".format(
                       input_probabilistic_dimension_name, original_cube))
            raise ValueError(msg)
    elif original_cube.coords(
            input_probabilistic_dimension_name, dim_coords=False):
        pass
    else:
        msg = ("A {} coordinate is not available on the {} cube.".format(
               input_probabilistic_dimension_name, original_cube))
        raise CoordinateNotFoundError(msg)
    shape_to_reshape_to = (
        [output_probabilistic_dimension_length] + shape_to_reshape_to)
    return array_to_reshape.reshape(shape_to_reshape_to)