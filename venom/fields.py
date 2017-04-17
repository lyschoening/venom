import collections
from abc import ABCMeta
from importlib import import_module

from typing import TypeVar, Generic, Any, Union, Type, Sequence, List

from venom.util import cached_property, AttributeDict, camelcase

T = TypeVar('T', bool, int, float, str, bytes, 'venom.message.Message')


class FieldDescriptor(Generic[T], metaclass=ABCMeta):
    _name: str = None
    _json_name: str = None

    def __init__(self, name: str = None, *, json_name: str = None):
        self._name = name
        self._json_name = json_name

    def __get__(self, instance: 'venom.message.Message', owner):
        if instance is None:
            return self
        try:
            return instance[self.name]
        except KeyError:
            return self.default()

    def default(self):
        return None

    def __set_name__(self, owner, name):
        if self._name is None:
            self._name = name

    @property
    def json_name(self):
        if self._json_name is None:
            return camelcase(self.name)
        return self._json_name

    @property
    def name(self):
        return self._name

    # TODO wait on https://github.com/python/mypy/issues/244
    def __set__(self, instance: 'venom.message.Message', value: T):
        instance[self.name] = value

        # TODO Use Python 3.6 __set_name__()


class Field(Generic[T], FieldDescriptor):
    def __init__(self,
                 type_: Union[Type[T], str],
                 default: Any = None,
                 name: str = None,
                 *,
                 json_name: str = None,
                 **options) -> None:
        super(Field, self).__init__(name, json_name=json_name)
        self._type = type_
        self._default = default
        self.options = AttributeDict(options)

    def default(self):
        if self._default is None:
            return self.type()
        return self._default

    @cached_property
    def type(self) -> Type[T]:
        if isinstance(self._type, str):
            if '.' in self._type:
                module_name, class_name = self._type.rsplit('.', 1)
                module = import_module(module_name)
                return getattr(module, class_name)

            raise RuntimeError('Unable to resolve: {} in {}'.format(self._type, repr(self)))
        return self._type

    def __eq__(self, other):
        if not isinstance(other, Field):
            return False
        return self.type == other.type and self.options == other.options

    def __repr__(self):
        type_ = self._type.__qualname__ if not isinstance(self._type, str) else repr(self._type)
        if self.name:
            return f'<{self.__class__.__qualname__} {self.name}:{type_}>'
        return f'<{self.__class__.__qualname__} {type_}>'

    def __hash__(self):
        return hash(repr(self))


P = TypeVar('P')


class ConverterField(Generic[T, P], Field[T]):
    def __init__(self,
                 converter: 'venom.converter.Converter[T, P]' = None,
                 **kwargs) -> None:
        super().__init__(converter.wire, **kwargs)
        self.converter = converter

    def __set__(self, instance: T, value: P) -> None:
        instance[self.name] = self.converter.format(value)

    def __get__(self, instance: T, _=None) -> P:
        return self.converter.convert(instance.get(self.name))


class String(Field[str]):
    def __init__(self, **kwargs) -> None:
        super().__init__(str, **kwargs)


class Bytes(Field[bytes]):
    def __init__(self, **kwargs) -> None:
        super().__init__(bytes, **kwargs)


class Bool(Field[bool]):
    def __init__(self, **kwargs) -> None:
        super().__init__(bool, **kwargs)


class Int32(Field[int]):
    def __init__(self, **kwargs) -> None:
        super().__init__(int, **kwargs)


class Int64(Field[int]):
    def __init__(self, **kwargs) -> None:
        super().__init__(int, **kwargs)


Integer = Int = Int64


class Float32(Field[float]):
    def __init__(self, **kwargs) -> None:
        super().__init__(float, **kwargs)


class Float64(Field[float]):
    def __init__(self, **kwargs) -> None:
        super().__init__(float, **kwargs)


Number = Float64

CT = TypeVar('CT', Field, 'MapField', 'RepeatField')


class _RepeatValueProxy(collections.MutableSequence):
    def __init__(self, message: 'venom.message.Message', name: str):
        self.message = message
        self.name = name

    @property
    def _sequence(self) -> list:
        try:
            return self.message[self.name]
        except KeyError:
            return list()

    def __len__(self):
        return len(self._sequence)

    def __getitem__(self, index):
        return self._sequence[index]

    def insert(self, index, value):
        self.message[self.name] = sequence = self._sequence
        sequence.insert(index, value)

    def __delitem__(self, index):
        self.message[self.name] = sequence = self._sequence
        del sequence[index]

    def __setitem__(self, index, value):
        self.message[self.name] = sequence = self._sequence
        sequence[index] = value

    def __iter__(self):
        return iter(self._sequence)


class RepeatField(Generic[CT], FieldDescriptor):
    def __init__(self, items: Type[CT], name: str = None, *, json_name: str = None, **options) -> None:
        super().__init__(name, json_name=json_name)
        self.items = items
        self.options = AttributeDict(options)

    def __get__(self, instance: 'venom.message.Message', owner):
        if instance is None:
            return self
        return _RepeatValueProxy(instance, self.name)

    def __eq__(self, other):
        if not isinstance(other, RepeatField):
            return False
        return self.items == other.items and self.name == other.name and self.options == other.options

    def __repr__(self):
        return '<{} {} {}>'.format(self.__class__.__name__, self.name, str(self.items))


class MapField(Generic[CT], FieldDescriptor):
    def __init__(self, values: Type[CT], name: str = None, *, json_name: str = None, **options) -> None:
        super().__init__(name, json_name=json_name)
        self.keys = String()
        self.values = values
        self.options = AttributeDict(options)


def Repeat(items: Union[Field, MapField, RepeatField, type, str], **kwargs) -> RepeatField:
    if isinstance(items, type) and issubclass(items, Field):
        items = items()
    if not isinstance(items, (Field, MapField, RepeatField)):
        items = Field(items)
    return RepeatField(items, **kwargs)


def Map(values: Union[Field, MapField, RepeatField, type, str], **kwargs) -> MapField:
    # TODO keys argument.
    return MapField(values, **kwargs)


def create_field_from_type_hint(hint,
                                converters: Sequence['venom.converter.Converter'] = (),
                                default: Any = None,
                                name: str = None):
    if hint in (bool, int, float, str, bytes):
        return Field(hint, default=default, name=name)

    for converter in converters:
        if converter.python == hint:
            return ConverterField(converter, name=name)

    # TODO support 'Repeat' as alias for list.
    # TODO type_ != Any is a workaround for https://github.com/python/typing/issues/345
    if hint != Any and issubclass(hint, List):
        # FIXME List[List[X]] must not become Repeat(Repeat(X))
        return Repeat(create_field_from_type_hint(hint.__args__[0]), name=name)

    # TODO support Map, Mapping and Dict

    from venom import Message
    # TODO type_ != Any is a workaround for https://github.com/python/typing/issues/345
    if hint != Any and issubclass(hint, Message):
        return Field(hint, name=name)

    raise NotImplementedError(f"Unable to generate field for {hint}")
