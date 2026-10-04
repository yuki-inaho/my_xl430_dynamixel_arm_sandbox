#include <nanobind/nanobind.h>
#include <nanobind/eigen/dense.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/pair.h>
#include "core.hpp"
namespace nb=nanobind;
using namespace articulated_filterreg;
NB_MODULE(_native,m) {
    m.doc()="Articulated FilterReg Gaussian moments and per-link similarity blocks";
    nb::class_<MomentFilter>(m,"MomentFilter")
        .def(nb::init<const Matrix&,double,bool>(),nb::arg("observations"),nb::arg("sigma"),nb::arg("exact")=false)
        .def("evaluate",&MomentFilter::evaluate,nb::call_guard<nb::gil_scoped_release>());
    m.def("assemble_blocks",[](const Matrix& p,const Matrix& mu,const Vector& w,
        const Eigen::VectorXi& body,const std::vector<Matrix>& maps){
        auto result=assemble_blocks(p,mu,w,body,maps);
        return std::make_pair(std::move(result.hessian),std::move(result.gradient));
    },nb::call_guard<nb::gil_scoped_release>());
    m.attr("binding")="nanobind";
}
