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
"""Module to contain operations along a vertical dimension."""

import numpy as np

import iris


class VerticalIntegration(object):
    """Perform integration along a chosen coordinate."""

    def __init__(self, coord_name_to_integrate,
                 start_point=None, end_point=None,
                 direction_of_integration="upwards"):
        """
        Initialise class.

        Args:
            coord_name_to_integrate (iris.cube.Cube):
                Name of the coordinate to be integrated.
            start_point (float or None):
                Point at which to start the interpolation.
                Default is None.
            end_point (float or None):
                Point at which to end the interpolation.
                Default is None.
            direction_of_integration (string):
                Description of the direction in which to integrate.
                Options are 'upwards' or 'downwards'.
        """
        self.coord_name_to_integrate = coord_name_to_integrate
        self.start_point = start_point
        self.end_point = end_point
        self.direction_of_integration = direction_of_integration
        if self.direction_of_integration not in ["upwards", "downwards"]:
            msg = ("The specified direction of integration should be either "
                   "'upwards' or 'downwards'. {} was specified.".format(
                       self.direction_of_integration))
            raise ValueError(msg)

    def __repr__(self):
        """Represent the configured plugin instance as a string."""
        result = ('<VerticalIntegration: coord_name_to_integrate: {}, '
                  'start_point: {}, end_point: {}, '
                  'direction_of_integration: {}>'.format(
                      self.coord_name_to_integrate, self.start_point,
                      self.end_point, self.direction_of_integration))
        return result

    def ensure_monotonic_in_chosen_direction(self, cube):
        """Ensure that the chosen coordinate is monotonically increasing in
        the specified direction.

        Args:
            cube (Iris.cube.Cube):
                The cube containing the coordinate to check.

        Returns:
            cube (Iris.cube.Cube):
                The cube containing a coordinate that is monotonically
                increasing in the desired direction.

        Raises:
            ValueError: The chosen coordinate is not monotonic.

        """
        coord_name = self.coord_name_to_integrate
        direction = self.direction_of_integration
        increasing_order = np.all(np.diff(cube.coord(coord_name).points) > 0)

        if increasing_order and direction == "upwards":
            pass
        elif increasing_order and direction == "downwards":
            cube.coord(coord_name).points = cube.coord(coord_name).points[::-1]
        elif not increasing_order and direction == "upwards":
            cube.coord(coord_name).points = cube.coord(coord_name).points[::-1]
        elif not increasing_order and direction == "downwards":
            pass
        return cube

    def process(self, cube):
        """Integrate in the vertical. This is calculated by defining an upper
        and lower level using the chosen coordinate within the cube. The
        upper and lower levels define a layer.

        Integration is performed by firstly defining the layer_depth as the
        difference between the upper and lower level. The contribution from
        the top half of the layer is calculated by multiplying the upper level
        value by 0.5 * layer_depth, and the contribution from the bottom half
        of the layer is calculated by multiplying the bottom level value by
        0.5 * layer_depth. The contribution from the top half of the layer
        and the bottom half of the layer is summed.

        As the column is being integrated, the layers are cumulatively summed.

        Args:
            cube (Iris.cube.Cube):
                The cube containing the coordinate to check.

        Returns:
            integrated_cube (Iris.cube.Cube):
                The cube containing the result of the vertical integration.
                This will contain the same metadata as the input cube.

        """
        # Define upper and lower level cubes for the integration.
        upper_levels = cube.coord(self.coord_name_to_integrate).points[:-1]
        lower_levels = cube.coord(self.coord_name_to_integrate).points[1:]
        upper_level_cube = (
             cube.extract(
                 iris.Constraint(
                     coord_values={self.coord_name_to_integrate:
                                   upper_levels})))
        lower_level_cube = (
            cube.extract(
                iris.Constraint(
                    coord_values={self.coord_name_to_integrate:
                                  lower_levels})))

        # Make coordinate monotonic in the direction desired for integration.
        upper_level_cube = (
            self.ensure_monotonic_in_chosen_direction(upper_level_cube))
        lower_level_cube = (
            self.ensure_monotonic_in_chosen_direction(lower_level_cube))
        integrated_cube = lower_level_cube.copy()

        # Create a tuple for looping over.
        levels_tuple = zip(
            upper_level_cube.slices_over(self.coord_name_to_integrate),
            lower_level_cube.slices_over(self.coord_name_to_integrate),
            integrated_cube.slices_over(self.coord_name_to_integrate))

        layer_sum = 0
        for (upper_level_slice, lower_level_slice,
                 integrated_slice) in levels_tuple:
            upper_depth = (
                upper_level_slice.coord(self.coord_name_to_integrate).points)
            lower_depth = (
                lower_level_slice.coord(self.coord_name_to_integrate).points)
            if ((self.start_point and upper_depth < self.start_point) or
                    (self.end_point and lower_depth > self.end_point)):
                layer_depth = upper_depth - lower_depth
                top_half_of_layer = (
                    upper_level_slice.data * 0.5 * layer_depth)
                bottom_half_of_layer = (
                    lower_level_slice.data * 0.5 * layer_depth)
                layer_sum += bottom_half_of_layer + top_half_of_layer
                integrated_slice.data = layer_sum
        return integrated_cube
