#include "core.hpp"
#include <cmath>
#include <stdexcept>

namespace articulated_filterreg {
namespace {
void cloud(const Matrix& p,const char* name) {
    if(p.rows()==0 || p.cols()!=3 || !p.allFinite())
        throw std::invalid_argument(std::string(name)+" must be finite nonempty (n,3)");
}
}
MomentFilter::MomentFilter(const Matrix& y,double sigma,bool exact)
    :observations_(y),sigma_(sigma),exact_(exact) {
    cloud(y,"observations");
    if(!std::isfinite(sigma)||sigma<=0) throw std::invalid_argument("sigma must be finite and positive");
    center_=y.colwise().mean();
    values_.resize(y.rows(),5);values_.col(0).setOnes();values_.middleCols(1,3)=y;
    values_.col(4)=y.rowwise().squaredNorm();
    if(!exact_) {
        Matrix features=(y.rowwise()-center_)/sigma;
        lattice_=std::make_unique<acpd::FixedNoBlurLattice>(features,values_);
    }
}
Matrix MomentFilter::evaluate(const Matrix& x) const {
    cloud(x,"queries");
    if(exact_) {
        Matrix out=Matrix::Zero(x.rows(),5);
        const double inverse=0.5/(sigma_*sigma_);
        for(Eigen::Index i=0;i<x.rows();++i)
            for(Eigen::Index j=0;j<observations_.rows();++j) {
                const double k=std::exp(-(x.row(i)-observations_.row(j)).squaredNorm()*inverse);
                out.row(i).noalias()+=k*values_.row(j);
            }
        return out;
    }
    Matrix features=(x.rowwise()-center_)/sigma_;
    return lattice_->slice(features);
}
NormalEquations assemble_blocks(const Matrix& p,const Matrix& mu,const Vector& w,
    const Eigen::VectorXi& body,const std::vector<Matrix>& S) {
    cloud(p,"points");cloud(mu,"targets");
    if(mu.rows()!=p.rows()||w.size()!=p.rows()||body.size()!=p.rows()||!w.allFinite()||(w.array()<0).any())
        throw std::invalid_argument("target, weight, body dimensions or values are invalid");
    if(S.empty()) throw std::invalid_argument("at least one body map is required");
    const Eigen::Index d=S.front().cols();
    if(d<1||d>128) throw std::invalid_argument("invalid joint parameter count");
    for(const auto& s:S) if(s.rows()!=7||s.cols()!=d||!s.allFinite())
        throw std::invalid_argument("each space map must have finite shape (7,d)");
    using H7=Eigen::Matrix<double,7,7>;using V7=Eigen::Matrix<double,7,1>;
    std::vector<H7> H(S.size(),H7::Zero());std::vector<V7> g(S.size(),V7::Zero());
    for(Eigen::Index i=0;i<p.rows();++i) {
        const int b=body[i];
        if(b<0||static_cast<std::size_t>(b)>=S.size()) throw std::invalid_argument("body index out of range");
        const double x=p(i,0),y=p(i,1),z=p(i,2);
        Eigen::Matrix<double,3,7> A;
        A<<0,z,-y,1,0,0,x, -z,0,x,0,1,0,y, y,-x,0,0,0,1,z;
        H[b].noalias()+=w[i]*(A.transpose()*A);
        g[b].noalias()+=w[i]*A.transpose()*(mu.row(i)-p.row(i)).transpose();
    }
    NormalEquations out{Matrix::Zero(d,d),Vector::Zero(d)};
    for(std::size_t b=0;b<S.size();++b) {
        out.hessian.noalias()+=S[b].transpose()*H[b]*S[b];
        out.gradient.noalias()+=S[b].transpose()*g[b];
    }
    if(!out.hessian.allFinite()||!out.gradient.allFinite()) throw std::runtime_error("nonfinite normal equations");
    return out;
}
}
