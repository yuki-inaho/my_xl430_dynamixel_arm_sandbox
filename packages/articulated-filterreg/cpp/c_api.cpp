// Explicit C-ABI adapter for constrained environments. This is NOT nanobind.
#include "core.hpp"
#include <string>
#include <exception>
using namespace articulated_filterreg;
namespace { thread_local std::string error;
using RowMatrix=Eigen::Matrix<double,Eigen::Dynamic,Eigen::Dynamic,Eigen::RowMajor>;
}
extern "C" {
const char* af_last_error() noexcept { return error.c_str(); }
void* af_create(const double* y,int n,double sigma,int exact) noexcept {
    try {
        error.clear();if(!y||n<=0) throw std::invalid_argument("invalid observations");
        return new MomentFilter(Eigen::Map<const RowMatrix>(y,n,3),sigma,exact!=0);
    } catch(const std::exception& e) {error=e.what();return nullptr;}
}
void af_destroy(void* handle) noexcept {delete static_cast<MomentFilter*>(handle);}
int af_evaluate(void* handle,const double* x,int n,double* out) noexcept {
    try {
        error.clear();if(!handle||!x||!out||n<=0) throw std::invalid_argument("invalid evaluate arguments");
        Eigen::Map<RowMatrix>(out,n,5)=static_cast<MomentFilter*>(handle)->evaluate(Eigen::Map<const RowMatrix>(x,n,3));
        return 0;
    } catch(const std::exception& e) {error=e.what();return -1;}
}
int af_assemble(const double* p,const double* mu,const double* w,const int* body,int n,
    const double* maps,int nb,int d,double* h,double* g) noexcept {
    try {
        error.clear();if(!p||!mu||!w||!body||!maps||!h||!g||n<=0||nb<=0||d<=0)
            throw std::invalid_argument("invalid assemble arguments");
        std::vector<Matrix> S;S.reserve(nb);
        for(int b=0;b<nb;++b) S.emplace_back(Eigen::Map<const RowMatrix>(maps+b*7*d,7,d));
        auto out=assemble_blocks(Eigen::Map<const RowMatrix>(p,n,3),Eigen::Map<const RowMatrix>(mu,n,3),
            Eigen::Map<const Vector>(w,n),Eigen::Map<const Eigen::VectorXi>(body,n),S);
        Eigen::Map<RowMatrix>(h,d,d)=out.hessian;Eigen::Map<Vector>(g,d)=out.gradient;return 0;
    } catch(const std::exception& e) {error=e.what();return -1;}
}
}
