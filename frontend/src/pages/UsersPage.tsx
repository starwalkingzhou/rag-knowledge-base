import {useState} from 'react'
import {
    App,
    Button,
    Form,
    Input,
    Modal,
    Popconfirm,
    Select,
    Table,
    Tag,
} from 'antd'
import {DeleteOutlined, EditOutlined, PlusOutlined} from '@ant-design/icons'
import type {ColumnsType} from 'antd/es/table'

import {
    useAssignRolesMutation,
    useCreateUserMutation,
    useDeleteUserMutation,
    useUpdateUserMutation,
    useUsers,
} from '@/api/users'
import {useRoles} from '@/api/roles'
import {useAuthStore} from '@/store/authStore'
import type {RoleRead, UserRead} from '@/client/types.gen'

interface CreateFormValues {
    username: string
    password: string
    display_name: string
    role_ids: string[]
}

interface EditFormValues {
    display_name: string
    status: 'active' | 'disabled'
    password: string
    role_ids: string[]
}

function CreateUserModal({
                             open,
                             onClose,
                             roles,
                         }: {
    open: boolean
    onClose: () => void
    roles: RoleRead[] | undefined
}) {
    const {message} = App.useApp()
    const createMutation = useCreateUserMutation()
    const [form] = Form.useForm<CreateFormValues>()

    return (
        <Modal
            title="新建用户"
            open={open}
            onCancel={() => {
                form.resetFields()
                onClose()
            }}
            destroyOnHidden
            onOk={async () => {
                const values = await form.validateFields()
                await createMutation.mutateAsync(values)
                message.success('用户已创建')
                form.resetFields()
                onClose()
            }}
            confirmLoading={createMutation.isPending}
            okText="创建"
        >
            <Form form={form} layout="vertical" initialValues={{role_ids: []}}>
                <Form.Item name="username" label="用户名"
                           rules={[{required: true, message: '请输入用户名'}]}>
                    <Input placeholder="登录账号" autoFocus/>
                </Form.Item>
                <Form.Item name="password" label="密码"
                           rules={[{required: true, message: '请输入密码'}]}>
                    <Input.Password placeholder="初始密码"/>
                </Form.Item>
                <Form.Item name="display_name" label="显示名"
                           rules={[{required: true, message: '请输入显示名'}]}>
                    <Input placeholder="用户昵称"/>
                </Form.Item>
                <Form.Item name="role_ids" label="角色">
                    <Select
                        mode="multiple"
                        placeholder="选择角色"
                        options={(roles ?? []).map(r => ({value: r.id, label: r.name}))}
                    />
                </Form.Item>
            </Form>
        </Modal>
    )
}

function EditUserModal({
                           open,
                           onClose,
                           target,
                           roles,
                       }: {
    open: boolean
    onClose: () => void
    target: UserRead | null
    roles: RoleRead[] | undefined
}) {
    const {message} = App.useApp()
    const updateMutation = useUpdateUserMutation()
    const assignMutation = useAssignRolesMutation()
    const [form] = Form.useForm<EditFormValues>()

    async function onFinish(values: EditFormValues) {
        if (!target) return
        try {
            await updateMutation.mutateAsync({
                userId: target.id,
                payload: {
                    display_name: values.display_name,
                    status: values.status,
                    password: values.password || null,
                },
            })
            await assignMutation.mutateAsync({
                userId: target.id,
                payload: {role_ids: values.role_ids},
            })
            message.success('已保存')
            form.resetFields()
            onClose()
        } catch {
            // 拦截器已弹错误
        }
    }

    return (
        <Modal
            title={`编辑用户 ${target?.username ?? ''}`}
            open={open}
            onCancel={() => {
                form.resetFields()
                onClose()
            }}
            destroyOnHidden
            onOk={() => {
                void form.submit()
            }}
            confirmLoading={updateMutation.isPending || assignMutation.isPending}
            okText="保存"
        >
            <Form
                form={form}
                layout="vertical"
                initialValues={{
                    display_name: target?.display_name ?? '',
                    status: target?.status ?? 'active',
                    password: '',
                    role_ids: target?.roles?.map(r => r.id) ?? [],
                }}
                onFinish={onFinish}
            >
                <Form.Item name="display_name" label="显示名"
                           rules={[{required: true, message: '请输入显示名'}]}>
                    <Input/>
                </Form.Item>
                <Form.Item name="status" label="状态"
                           rules={[{required: true}]}>
                    <Select
                        options={[
                            {value: 'active', label: '启用'},
                            {value: 'disabled', label: '禁用'},
                        ]}
                    />
                </Form.Item>
                <Form.Item name="password" label="重置密码"
                           extra="留空则不修改">
                    <Input.Password placeholder="新密码"/>
                </Form.Item>
                <Form.Item name="role_ids" label="角色">
                    <Select
                        mode="multiple"
                        placeholder="选择角色"
                        options={(roles ?? []).map(r => ({value: r.id, label: r.name}))}
                    />
                </Form.Item>
            </Form>
        </Modal>
    )
}

function DeleteUserButton({
                              userId,
                              disabled,
                          }: {
    userId: string
    disabled: boolean
}) {
    const {message} = App.useApp()
    const mutation = useDeleteUserMutation()
    return (
        <Popconfirm
            title="删除该用户?"
            okType="danger"
            disabled={disabled}
            onConfirm={async () => {
                try {
                    await mutation.mutateAsync(userId)
                    message.success('已删除')
                } catch {
                    // 拦截器已弹错误
                }
            }}
        >
            <Button
                size="small"
                danger
                icon={<DeleteOutlined/>}
                disabled={disabled}
            >
                删除
            </Button>
        </Popconfirm>
    )
}

export function UsersPage() {
    const currentUser = useAuthStore(s => s.user)
    const [page, setPage] = useState(1)
    const pageSize = 20
    const {data, isLoading} = useUsers(page, pageSize)
    const rolesQuery = useRoles()
    const [createOpen, setCreateOpen] = useState(false)
    const [editTarget, setEditTarget] = useState<UserRead | null>(null)

    const currentUserId = currentUser?.id

    const columns: ColumnsType<UserRead> = [
        {title: '用户名', dataIndex: 'username', width: 120},
        {title: '显示名', dataIndex: 'display_name', width: 140},
        {
            title: '状态',
            dataIndex: 'status',
            width: 90,
            render: (status: string) => (
                <Tag color={status === 'active' ? 'success' : 'default'}>
                    {status === 'active' ? '启用' : '禁用'}
                </Tag>
            ),
        },
        {
            title: '角色',
            dataIndex: 'roles',
            width: 200,
            render: (roles: RoleRead[] | undefined) => (
                <span>
                    {(roles ?? []).map(r => (
                        <Tag key={r.id}>{r.name}</Tag>
                    ))}
                </span>
            ),
        },
        {
            title: '创建时间',
            dataIndex: 'created_at',
            width: 160,
            render: (v: string) => new Date(v).toLocaleString(),
        },
        {
            title: '操作',
            width: 140,
            render: (_, record) => (
                <span>
                    <Button
                        size="small"
                        icon={<EditOutlined/>}
                        style={{marginRight: 8}}
                        onClick={() => setEditTarget(record)}
                    >
                        编辑
                    </Button>
                    <DeleteUserButton
                        userId={record.id}
                        disabled={record.id === currentUserId}
                    />
                </span>
            ),
        },
    ]

    return (
        <div>
            <div style={{marginBottom: 16, display: 'flex', justifyContent: 'space-between'}}>
                <h2 style={{margin: 0}}>用户管理</h2>
                <Button
                    type="primary"
                    icon={<PlusOutlined/>}
                    onClick={() => setCreateOpen(true)}
                >
                    新建用户
                </Button>
            </div>
            <Table
                rowKey="id"
                loading={isLoading}
                columns={columns}
                dataSource={data?.items ?? []}
                pagination={{
                    current: page,
                    pageSize,
                    total: data?.total ?? 0,
                    onChange: p => setPage(p),
                    showSizeChanger: false,
                }}
            />
            <CreateUserModal
                open={createOpen}
                onClose={() => setCreateOpen(false)}
                roles={rolesQuery.data}
            />
            <EditUserModal
                open={editTarget !== null}
                onClose={() => setEditTarget(null)}
                target={editTarget}
                roles={rolesQuery.data}
            />
        </div>
    )
}
