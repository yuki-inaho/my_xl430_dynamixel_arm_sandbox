#pragma once
#include <Eigen/Core>
#include <memory>
#include <vector>
#include "acpd/lattice.hpp"

namespace articulated_filterreg {
using Matrix = Eigen::MatrixXd;
using Vector = Eigen::VectorXd;

// Gaussian E-step only. Observations remain fixed; model vertices are queries.
// Column layout: [M0, M1.x, M1.y, M1.z, M2].
class MomentFilter {
public:
    MomentFilter(const Matrix& observations, double sigma, bool exact);
    Matrix evaluate(const Matrix& queries) const;
private:
    Matrix observations_, values_;
    Eigen::RowVector3d center_;
    double sigma_;
    bool exact_;
    std::unique_ptr<acpd::FixedNoBlurLattice> lattice_;
};

struct NormalEquations { Matrix hessian; Vector gradient; };

// Reduce point contributions into a fixed 7x7 block per rigid link, THEN map
// each block into the joint parameter space. The seventh component is scale.
NormalEquations assemble_blocks(const Matrix& points, const Matrix& targets,
    const Vector& weights, const Eigen::VectorXi& body,
    const std::vector<Matrix>& space_maps);
}
