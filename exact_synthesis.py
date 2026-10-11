"""The exact synthesis thm 5.5"""

import math

import numpy as np
from constants import hh


def get_lde(col: np.ndarray) -> int:
    """
    Get the least denominator exponent of a column vector.

    Args:
        col: NumPy array containing exact Fraction entries.

    Returns:
        The smallest exponent q such that multiplying the column by 2**q
        gives only integer entries.
    """
    get_exponent = np.vectorize(
        lambda x: int(math.log2(x.denominator))
    )

    lde = np.max(get_exponent(col))

    return int(lde)

def manipulate_into_identity(
    matrix: np.ndarray,
    generator_list: list,
    trace=None,
) -> None:
    """
    Reduce a signed permutation matrix to the identity matrix.

    Args:
        matrix: Working matrix whose columns are signed basis vectors.
        generator_list: List used to record applied generators.

    Returns:
        None. The matrix and generator list are modified in place.
    """
    for i in range(len(matrix)):
        if trace is not None:
            trace.start_column(matrix, i, 0, phase="normalize")
        col = matrix[:, i]

        nonzero_indices = np.flatnonzero(col != 0)
        row = int(nonzero_indices[0])

        if row != i:
            matrix[[i, row], :] = matrix[[row, i], :]

            generator_list.append({
                "type": "swap",
                "indices": [i, row]
            })
            if trace is not None:
                trace.operation(matrix, generator_list[-1], role="permutation")

        if matrix[i, i] == -1:
            matrix[i, :] *= -1

            generator_list.append({
                "type": "sign_flip",
                "indices": [i]
            })
            if trace is not None:
                trace.operation(matrix, generator_list[-1], role="terminal_sign")

        if trace is not None:
            trace.column_complete(matrix, i)

def synthesize(matrix: np.ndarray, trace=None) -> list:
    """
    Reduce a unitary matrix over the dyadic ring to the identity using the
    generators from the exact synthesis algorithm of Theorem 5.5.

    The algorithm applies Lemma 5.3 repeatedly to reduce the least denominator
    exponent of each column. Lemma 5.2 is used on groups of four odd entries
    during each reduction step. Once the denominator exponent reaches zero,
    the base case of Lemma 5.4 reduces the resulting signed basis vectors to
    the corresponding positive basis vectors.

    Args:
        matrix: Unitary matrix with exact Fraction entries over the dyadic ring.

    Returns:
        ordered list of generators applied during the reduction.
    """
    generator_list = [] # [{type: "sign_flip", indices: [int(index)]}, {"type": "hh","indices": [int(i) for i in group]}]
    # Theorem 5.5: iteratively apply Lemma 5.4 to reduce each column
    # into its corresponding positive basis vector.
    # our goal is to reduce each col into a positive basis vector
    for i in range(len(matrix)): 
        # get lde using log base 2 on denominator
        col = matrix[:,i]
        lde = get_lde(col)
        if trace is not None:
            trace.start_column(matrix, i, lde, phase="integral")
        while lde != 0:   
            # Lemma 5.3: reduce the least denominator exponent of the column.

            # divide col entries by 2**lde
            scaled_col = np.vectorize(int)(col*(2**lde))

            # collect group of 4 odd numbers
            # side note from the proof here. In Lemma 5.3 we see that:
            #   sum(u**2) = 4**q 
            #   sum(u**2) mod 4 = (4**q) mod 4
            #   sum(u**2) mod 4 = 0 
            # the only way for that to work requires is either group of 4 is even
            # or we have multiple of 4 odd numbers ex 1+1+1+1 = 4 mod 4 = 0
            # hence we dont need to worry about having odd size like 6 odd numbers
            odd_indices = np.flatnonzero(scaled_col % 2 != 0)
            odd_groups_of_4_indices = odd_indices.reshape(-1, 4)
            odd_groups_of_4 = scaled_col[odd_groups_of_4_indices]
            
            # Lemma 5.2 specifies the following
            # if we have an odd int u**2 mod 4 = 1 => u is congruent to 1 or 3
            # we want everything mod 4 so we can turn it into a basis vector
            # we will multipliy our entries of u with (-1) (flip them) if they are congruent 3 mod 4
            # this will make it congruent 1 mod 4
            # this is setting it up for the HxH gate to turn it into a vector with even
            # values so we can continue to reduce the lde again
            mask = odd_groups_of_4 % 4 == 3
            sign_flip_indices = odd_groups_of_4_indices[mask]
            if trace is not None:
                trace.start_sweep(
                    matrix, lde, scaled_col, odd_indices,
                    odd_groups_of_4_indices, sign_flip_indices,
                )

            for index in sign_flip_indices:
                matrix[index, :] *= -1

                generator_list.append({
                    "type": "sign_flip",
                    "indices": [int(index)]
                })
                if trace is not None:
                    trace.operation(matrix, generator_list[-1], role="sign_correction")

            # Lemma 5.2: apply HxH to each group of four odd entries.
            # Apply HxH gate which is going to make them even
            for group in odd_groups_of_4_indices:
                matrix[group, :] = hh @ matrix[group, :]

                generator_list.append({
                    "type": "hh",
                    "indices": [int(index) for index in group]
                })
                if trace is not None:
                    trace.operation(matrix, generator_list[-1], role="mixing")

            # Lemma 5.3 guarantees that the least denominator exponent
            # has decreased after all groups have been processed.
            lde = get_lde(matrix[:, i])
            if trace is not None:
                trace.finish_sweep(matrix, lde)

        if trace is not None:
            trace.column_integral(matrix, i)

    # Lemma 5.4 base case: once lde = 0, each unit column is a signed basis vector.
    # we now have matrix in the form of +-basis vector (1 0 0 0 0 0 ...)
    # to turn this into the identity we need to get rid of those nasty
    # negatives with sign flips again and the we will need to use X gates 
    # to use X[a,b] (a two leve swap generator) to swap rows so we can get 1 at the diagonals and 0s
    # everywhere else which is going to give us the identity matrix
    manipulate_into_identity(matrix, generator_list, trace=trace)
    
    return generator_list