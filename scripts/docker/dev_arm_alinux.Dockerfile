FROM alibaba-cloud-linux-3-registry.cn-hangzhou.cr.aliyuncs.com/alinux3/alinux3:latest

ARG PY_VER=3.8

RUN echo $'[alinux3-module] \n\
name=alinux3-module \n\
baseurl=http://mirrors.cloud.aliyuncs.com/alinux/$releasever/module/$basearch/ \n\
gpgkey=http://mirrors.cloud.aliyuncs.com/alinux/$releasever/RPM-GPG-KEY-ALINUX-3 \n\
enabled=1 \n\
gpgcheck=1' > /etc/yum.repos.d/alinux3-module.repo

RUN echo $'[alinux3-os] \n\
name=alinux3-os \n\
baseurl=http://mirrors.cloud.aliyuncs.com/alinux/$releasever/os/$basearch/ \n\
gpgkey=http://mirrors.cloud.aliyuncs.com/alinux/$releasever/RPM-GPG-KEY-ALINUX-3 \n\
enabled=1 \n\
gpgcheck=1' > /etc/yum.repos.d/alinux3-os.repo

RUN yum install git git-lfs g++ make tar procps python3 wget -y --nogpgcheck
RUN yum install numactl glibc-devel openssl-devel curl-devel automake rpm-build -y --nogpgcheck

RUN echo -e "if [ -f /usr/share/bash-completion/bash_completion ]; then \n    . /usr/share/bash-completion/bash_completion \nfi\n" >> /root/.bashrc && source /root/.bashrc

RUN curl -LO https://repo.anaconda.com/miniconda/Miniconda3-py38_23.3.1-0-Linux-aarch64.sh \
    && bash Miniconda3-py38_23.3.1-0-Linux-aarch64.sh -b \
    && rm -f Miniconda3-py38_23.3.1-0-Linux-aarch64.sh

ENV PATH=${PATH}:/root/miniconda3/bin

# uncomment if want to use anaconda mirror
##########################################################################################################
# RUN conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/ && \
#     conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/ && \
#     conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge  && \
#     conda config --remove channels defaults && \
#     conda config --set show_channel_urls yes
##########################################################################################################

RUN conda clean -i && conda config --show channels && conda create -y --name ds_py python==${PY_VER} && conda update -n base conda
SHELL ["conda", "run", "-n", "ds_py", "/bin/bash", "-c"]
RUN echo "source activate ds_py" >> /root/.bashrc && source /root/.bashrc

RUN curl -LO https://github.com/Kitware/CMake/releases/download/v3.21.6/cmake-3.21.6-linux-aarch64.sh \
    && bash ./cmake-3.21.6-linux-aarch64.sh --skip-license --prefix=/usr \
    && rm -f cmake-3.21.6-linux-aarch64.sh

RUN curl -LO https://developer.arm.com/-/media/Files/downloads/hpc/arm-compiler-for-linux/22-1/arm-compiler-for-linux_22.1_RHEL-8_aarch64.tar \
    && tar -xvf arm-compiler-for-linux_22.1_RHEL-8_aarch64.tar \
    && sh arm-compiler-for-linux_22.1_RHEL-8/arm-compiler-for-linux_22.1_RHEL-8.sh -a \
    && rm -rf arm-compiler-for-linux_22.1_RHEL-8_aarch64.tar arm-compiler-for-linux_22.1_RHEL-8_aarch64

RUN echo "export ARM_COMPILER_ROOT=/opt/arm/arm-linux-compiler-22.1_Generic-AArch64_RHEL-8_aarch64-linux" >> /root/.bashrc && source /root/.bashrc
ENV PATH=${PATH}:/opt/arm/arm-linux-compiler-22.1_Generic-AArch64_RHEL-8_aarch64-linux/bin

# uncomment if want to use pip mirror
##########################################################################################################
# RUN mkdir -p /root/.pip && \
# echo $'[global] \n\
# index-url = https://mirrors.aliyun.com/pypi/simple/ \n' > /root/.pip/pip.conf
##########################################################################################################

RUN pip3 install --upgrade pip && pip3 install -U setuptools

# engine requirements
RUN pip3 install torch==2.0.1 transformers==4.38.0 protobuf==3.18.0 conan==1.60.0 pytest tokenizers scons wheel

# demo requirements
RUN pip3 install modelscope tabulate gradio

# model requirements
RUN pip3 install sentencepiece accelerate transformers_stream_generator tiktoken

# build tools
RUN conda install -y pybind11

WORKDIR /root/