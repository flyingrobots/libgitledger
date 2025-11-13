#[=======================================================================[
  verify_doxygen.cmake -- CTest helper

  Invoked via:
    cmake -DGL_DOC_OUT=<expected-index-html> -P cmake/verify_doxygen.cmake

  It builds the 'doxygen' target in the current binary dir and then asserts
  that the expected output file exists.
#]=======================================================================]

if(NOT DEFINED CMAKE_BINARY_DIR)
  message(FATAL_ERROR "CMAKE_BINARY_DIR is not defined")
endif()

if(NOT DEFINED GL_DOC_OUT)
  message(FATAL_ERROR "GL_DOC_OUT is required (path to html/index.html)")
endif()

execute_process(
  COMMAND "${CMAKE_COMMAND}" --build "${CMAKE_BINARY_DIR}" --target doxygen
  RESULT_VARIABLE build_rv
)
if(NOT build_rv EQUAL 0)
  message(FATAL_ERROR "Building 'doxygen' target failed with code ${build_rv}")
endif()

if(NOT EXISTS "${GL_DOC_OUT}")
  message(FATAL_ERROR "Expected Doxygen output not found: ${GL_DOC_OUT}")
endif()

message(STATUS "Doxygen output verified at: ${GL_DOC_OUT}")

