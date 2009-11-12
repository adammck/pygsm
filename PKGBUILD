# Contributor: Adam Mckaig <adam.mckaig@gmail.com>
# vim: ts=4 sts=4 et sw=4

pkgname="python-pygsm"
pkgver=0.1
pkgrel=1
pkgdesc="Python interface to GSM modems"
url="http://github.com/adammck/pygsm"
arch=("any")
license=("BSD")
depends=("python" "python-pyserial")
options=(!emptydirs)
source=("http://github.com/adammck/pygsm/tarball/0.1")
md5sums=("ae2a32976c17b94773dcc7ec062796a9")
install=

build() {
    cd $srcdir/adammck-pygsm-527189e
    python setup.py install --root=$pkgdir --optimize=1 || return 1
}
