from .abstract_layer import LayerBase, NoParamMixin
from ..util import zX, zX_like, white


class PoolLayer(NoParamMixin, LayerBase):

    def __init__(self, fdim, compiled=True):
        LayerBase.__init__(self, activation="linear", trainable=False)
        if compiled:
            print("Compiling PoolLayer...")
            from ..llatomic.lltensor_op import MaxPoolOp
        else:
            from ..atomic import MaxPoolOp
        self.fdim = fdim
        self.filter = None
        self.op = MaxPoolOp()

    def connect(self, to, inshape):
        ic, iy, ix = inshape[-3:]
        if any((iy % self.fdim, ix % self.fdim)):
            raise RuntimeError(
                "Incompatible shapes: {} % {}".format((ix, iy), self.fdim)
            )
        LayerBase.connect(self, to, inshape)
        self.output = zX(ic, iy // self.fdim, ix // self.fdim)

    def feedforward(self, questions):
        """
        Implementation of a max pooling layer.

        :param questions: numpy.ndarray, a batch of outsize from the previous layer
        :return: numpy.ndarray, max pooled batch
        """
        self.output, self.filter = self.op.apply(questions, self.fdim)
        return self.output

    def backpropagate(self, error):
        """
        Calculates the error of the previous layer.
        :param error:
        :return: numpy.ndarray, the errors of the previous layer
        """
        return self.op.backward(error, self.filter)

    @property
    def outshape(self):
        return self.output.shape[-3:]

    def __str__(self):
        return "Pool-{}x{}".format(self.fdim, self.fdim)


class ConvLayer(LayerBase):

    def __init__(self, nfilters, filterx=3, filtery=3, **kw):
        LayerBase.__init__(self, activation=kw.get("activation", "linear"), **kw)
        self.nfilters = nfilters
        self.fx = filterx
        self.fy = filtery
        self.depth = 0
        self.stride = 1
        self.inshape = None
        self.op = None

    def connect(self, to, inshape):
        if self.compiled:
            print("Compiling ConvLayer...")
            from ..llatomic.lltensor_op import ConvolutionOp
        else:
            from ..atomic import ConvolutionOp
        depth, iy, ix = inshape[-3:]
        if any((iy < self.fy, ix < self.fx)):
            raise RuntimeError(
                "Incompatible shapes: iy ({}) < fy ({}) OR ix ({}) < fx ({})"
                .format(iy, self.fy, ix, self.fx)
            )
        LayerBase.connect(self, to, inshape)
        self.op = ConvolutionOp()
        self.inshape = inshape
        self.depth = depth
        self.weights = white(self.nfilters, self.depth, self.fy, self.fx)
        self.biases = zX(self.nfilters)
        self.nabla_b = zX_like(self.biases)
        self.nabla_w = zX_like(self.weights)

    def feedforward(self, X):
        self.inputs = X
        self.output = self.activation(self.op.apply(X, self.weights, "valid"))
        return self.output

    def backpropagate(self, error):
        error *= self.activation.derivative(self.output)
        self.nabla_w = self.op.apply(
            self.inputs.transpose(1, 0, 2, 3),
            error.transpose(1, 0, 2, 3),
            mode="valid"
        ).transpose(1, 0, 2, 3)
        # self.nabla_b = error.sum()  # TODO: why is this commented out???
        rW = self.weights[:, :, ::-1, ::-1].transpose(1, 0, 2, 3)
        return self.op.apply(error, rW, "full")

    @property
    def outshape(self):
        oy, ox = tuple(ix - fx + 1 for ix, fx in zip(self.inshape[-2:], (self.fx, self.fy)))
        return self.nfilters, ox, oy

    def __str__(self):
        return "Conv({}x{}x{})-{}".format(self.nfilters, self.fy, self.fx, str(self.activation)[:4])
